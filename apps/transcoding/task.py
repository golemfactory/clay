import abc
import logging
import os
from typing import Any, Dict, Tuple, Optional

import golem_messages.message

from apps.core.task.coretask import CoreTask, CoreTaskBuilder, CoreTaskTypeInfo
from apps.core.task.coretaskstate import Options, TaskDefinition
from .common import AudioCodec, VideoCodec, Container, is_type_of, \
    TranscodingTaskBuilderException

import apps.transcoding.common
from apps.transcoding.ffmpeg.utils import StreamOperator
from apps.transcoding.common import TranscodingException

from golem.core.common import HandleError, timeout_to_deadline
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import Task
from golem.task.taskstate import SubtaskStatus


logger = logging.getLogger(__name__)


class TranscodingTaskOptions(Options):
    class AudioParams:
        def __init__(self, codec: AudioCodec = None, bitrate: str = None):
            self.codec = codec
            self.bitrate = bitrate

    class VideoParams:
        def __init__(self, codec: VideoCodec = None, bitrate: str = None,
                     frame_rate: int = None,
                     resolution: Tuple[int, int] = None):
            self.codec = codec
            self.bitrate = bitrate
            self.frame_rate = frame_rate
            self.resolution = resolution

    def __init__(self, use_playlist=False):
        super().__init__()
        self.video_params = TranscodingTaskOptions.VideoParams()
        self.audio_params = TranscodingTaskOptions.AudioParams()
        self.input_stream_path = None
        self.output_container = None
        self.use_playlist = use_playlist


class TranscodingTaskDefinition(TaskDefinition):
    def __init__(self):
        super(TranscodingTaskDefinition, self).__init__()
        self.options = TranscodingTaskOptions()


class TranscodingTask(CoreTask):
    def __init__(self, task_definition: TranscodingTaskDefinition, **kwargs):
        super(TranscodingTask, self).__init__(task_definition=task_definition,
                                              **kwargs)
        self.task_definition = task_definition

    def initialize(self, dir_manager: DirManager):
        super(TranscodingTask, self).initialize(dir_manager)
        logger.debug('Initialization of ffmpegTask')
        if len(self.task_resources) == 0:
            raise TranscodingException('There is no specified resources')
        stream_operator = StreamOperator()
        chunks = stream_operator.split_video(
            self.task_resources[0], self.task_definition.subtasks_count,
            dir_manager, self.task_definition.task_id)
        self.task_resources = chunks
        if len(chunks) < self.total_tasks:
            logger.warning('{} subtasks was requested but video splitting '
                           'process resulted in {} chunks.'
                           .format(self.total_tasks, len(chunks)))
        self.total_tasks = len(chunks)
        self.task_definition.subtasks_count = len(chunks)

    def accept_results(self, subtask_id, result_files):
        super(TranscodingTask, self).accept_results(subtask_id, result_files)
        self.num_tasks_received += 1

    def _get_next_subtask(self):
        logger.debug('Getting next task [type=trancoding, task_id={}]'.format(
            self.task_definition.task_id))
        subtasks = self.subtasks_given.values()
        subtasks = filter(lambda sub: sub['status'] in [
            SubtaskStatus.failure, SubtaskStatus.restarted], subtasks)
        failed_subtask = next(iter(subtasks), None)
        if failed_subtask:
            logger.debug('Subtask {} was failed, so let resent it'
                         .format(failed_subtask['subtask_id']))
            failed_subtask['status'] = SubtaskStatus.resent
            self.num_failed_subtasks -= 1
            return failed_subtask['subtask_num']
        else:
            assert self.last_task < self.total_tasks
            curr = self.last_task + 1
            self.last_task = curr
            return curr - 1

    def query_extra_data(self, perf_index: float, node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> Task.ExtraData:

        sid = self.create_subtask_id()

        subtask_num = self._get_next_subtask()
        subtask = {}
        transcoding_params = self._get_extra_data(subtask_num)
        # filter recursively None
        subtask['perf'] = perf_index
        subtask['node_id'] = node_id
        subtask['subtask_id'] = sid
        subtask['transcoding_params'] = transcoding_params
        subtask['subtask_num'] = subtask_num
        subtask['status'] = SubtaskStatus.starting

        self.subtasks_given[sid] = subtask

        return Task.ExtraData(ctd=self._get_task_computing_definition(
            sid, transcoding_params, perf_index))

    def query_extra_data_for_test_task(
            self) -> golem_messages.message.ComputeTaskDef:
        # TODO
        pass

    def _get_task_computing_definition(self, sid, transcoding_params, perf_idx):
        ctd = golem_messages.message.ComputeTaskDef()
        ctd['task_id'] = self.header.task_id
        ctd['subtask_id'] = sid
        ctd['extra_data'] = transcoding_params
        ctd['performance'] = perf_idx
        ctd['docker_images'] = [di.to_dict() for di in self.docker_images]
        ctd['deadline'] = min(timeout_to_deadline(self.header.subtask_timeout),
                              self.header.deadline)
        ctd['short_description'] = ''
        return ctd

    @abc.abstractmethod
    def _get_extra_data(self, subtask_num):
        pass


class TranscodingTaskBuilder(CoreTaskBuilder):
    # jako property
    SUPPORTED_FILE_TYPES = []
    SUPPORTED_VIDEO_CODECS = []
    SUPPORTED_AUDIO_CODECS = []
    TASK_CLASS = TranscodingTask

    @classmethod
    def build_full_definition(cls, task_type: CoreTaskTypeInfo,
                              dict: Dict[str, Any]):
        task_def = super().build_full_definition(task_type, dict)

        presets = cls._get_presets(task_def.options.input_stream_path)
        options = dict.get('options', {})
        video_options = options.get('video', {})
        audio_options = options.get('audio', {})

        ac = audio_options.get('codec')
        vc = video_options.get('codec')

        audio_params = TranscodingTaskOptions.AudioParams(
            AudioCodec.from_name(ac) if ac else None,
            audio_options.get('bit_rate'))

        video_params = TranscodingTaskOptions.VideoParams(
            VideoCodec.from_name(vc) if vc else None,
            video_options.get('bit_rate', presets.get('video_bit_rate')),
            video_options.get('frame_rate'),
            video_options.get('resolution'))

        output_container = Container.from_name(options.get(
            'container', presets.get('container')))

        cls._assert_codec_container_support(audio_params.codec,
                                            video_params.codec,
                                            output_container)
        task_def.options.video_params = video_params
        task_def.options.output_container = output_container
        task_def.options.audio_params = audio_params
        task_def.options.audio_params = audio_params
        task_def.options.name = dict.get('name', '')
        logger.debug('Transcoding task definition was build [definition={}]',
                     task_def.__dict__)
        return task_def

    @classmethod
    def _assert_codec_container_support(cls, audio_codec, video_codec,
                                        output_container):
        if audio_codec and audio_codec \
                not in output_container.get_supported_audio_codecs():
            raise TranscodingTaskBuilderException(
                'Container {} does not support {}'.format(
                    output_container.value, audio_codec.value))

        if video_codec and video_codec \
                not in output_container.get_supported_video_codecs():
            raise TranscodingTaskBuilderException(
                'Container {} does not support {}'.format(
                    output_container.value, video_codec.value))

    @classmethod
    def build_minimal_definition(cls, task_type: CoreTaskTypeInfo,
                                 dict: Dict[str, Any]):
        df = super(TranscodingTaskBuilder, cls).build_minimal_definition(
            task_type, dict)
        stream = cls._get_required_field(dict, 'resources', is_type_of(list))[0]
        df.options.input_stream_path = stream
        return df

    @classmethod
    @HandleError(ValueError, apps.transcoding.common.not_valid_json)
    @HandleError(IOError, apps.transcoding.common.file_io_error)
    def _get_presets(cls, path: str) -> Dict[str, Any]:
        if not os.path.isfile(path):
            raise TranscodingTaskBuilderException('{} does not exist'
                                                  .format(path))
        # FIXME get metadata by ffmpeg docker container
        # with open(path) as f:
        # return json.load(f)
        return {'container': 'mp4'}

    @classmethod
    def _get_required_field(cls, dict, key: str, validator=lambda _: True) \
            -> Any:
        v = dict.get(key)
        if not v or not validator(v):
            raise TranscodingTaskBuilderException(
                'Field {} is required in the task definition'.format(key))
        return v

    @classmethod
    def get_output_path(cls, dictionary, definition):
        parent = super(TranscodingTaskBuilder, cls)
        path = parent.get_output_path(dictionary, definition)
        options = cls._get_required_field(dictionary, 'options',
                                          is_type_of(dict))
        container = options.get('container', cls._get_presets(
            definition.options.input_stream_path))
        return '{}.{}'.format(path, container)


