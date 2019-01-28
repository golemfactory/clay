import abc
import copy
import logging
from multiprocessing import Lock
from typing import Any, Dict, Tuple, Optional

import golem_messages.message

from apps.core.task.coretask import CoreTask, CoreTaskBuilder, CoreTaskTypeInfo
from apps.core.task.coretaskstate import Options, TaskDefinition
from .common import AudioCodec, VideoCodec, Container
import apps.transcoding.common
from apps.transcoding.ffmpeg.utils import StreamOperator
from apps.transcoding.common import TranscodingException

from golem.core.common import HandleError, timeout_to_deadline
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import Task
from golem.task.taskstate import SubtaskStatus


logger = logging.getLogger(__name__)


class TranscodingTaskDefinition(TaskDefinition):
    class TranscodingAudioParams:
        def __init__(self, codec: AudioCodec, bitrate: int = None):
            self.codec = codec
            self.bitrate = bitrate

    class TranscodingVideoParams:
        def __init__(self, codec: VideoCodec, bit_rate = None, frame_rate: int = None,
                     resolution: Tuple[int, int] = None):
            self.codec = codec
            self.bit_rate = bit_rate
            self.frame_rate = frame_rate
            self.resolution = resolution

    def __init__(self, input_stream_path, audio_params, video_params,
                 output_container, task_id, parts):
        super().__init__()
        self.input_stream_path = input_stream_path
        self.audio_params = audio_params
        self.video_params = video_params
        self.output_container = output_container
        self.task_id = task_id
        self.subtasks_count = parts


class TranscodingTask(CoreTask):

    def __init__(self, task_definition: TranscodingTaskDefinition, **kwargs):
        logger.warning('kwargs = {}'.format(kwargs))
        super(TranscodingTask, self).__init__(task_definition=task_definition,
                                              **kwargs)
        self.task_definition = task_definition
        self.lock = Lock()

    def initialize(self, dir_manager: DirManager):
        super(TranscodingTask, self).initialize(dir_manager)

        if len(self.task_resources) == 0:
            raise TranscodingException('There is no specified resources')
        stream_operator = StreamOperator()
        chunks = stream_operator.split_video(
            self.task_resources[0], self.task_definition.subtasks_count, dir_manager,
            self.task_definition.task_id)
        self.task_resources = chunks
        # It may turn out that number of stream chunks after splitting
        # is less than requested number of subtasks
        self.total_tasks = len(chunks)

    def _get_next_subtask(self):
        with self.lock:
            subtasks = self.subtasks_given.values()
            subtasks = filter(lambda sub: sub['status'] in [
                SubtaskStatus.failure, SubtaskStatus.restarted], subtasks)
            failed_subtask = next(iter(subtasks), None)
            if failed_subtask:
                failed_subtask['status'] = SubtaskStatus.resent
                self.num_failed_subtasks -= 1
                return failed_subtask['subtask_num']
            else:
                assert self.last_task < self.total_tasks
                curr = self.last_task + 1
                self.last_task = curr # someone else read that field
                return curr

    def query_extra_data(self, perf_index: float, node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> Task.ExtraData:

        sid = self.create_subtask_id()

        subtask_num = self._get_next_subtask()
        subtask = {}
        transcoding_params = self._get_extra_data(subtask['subtask_num'])
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
        # TODO, FIXME
        pass

    def _refresh_existing_subtask(self, subtask):
        assert self.num_failed_subtasks > 0
        copied = copy.deepcopy(subtask)

        return copied

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
        super().build_full_definition(task_type, dict)
        input_stream_path = cls._get_required_field(dict, 'resources')
        presets = cls._get_presets(input_stream_path)
        options = dict.get('options', {})
        video_options = options.get('video', {})
        audio_options = options.get('audio', {})

        audio_params = TranscodingTaskDefinition.TranscodingAudioParams(
            AudioCodec.from_name(audio_options.get('codec')),
            audio_options.get('bit_rate'))

        video_params = TranscodingTaskDefinition.TranscodingVideoParams(
            VideoCodec.from_name(video_options.get('codec')),
            video_options.get('bit_rate', presets.get('video_bit_rate')))

        output_container = Container.from_name(options.get(
            'output_container', presets.get('container')))

        cls._assert_codec_container_support(audio_params.codec,
                                            video_params.codec,
                                            output_container)

        return TranscodingTaskDefinition(input_stream_path, audio_params,
                                         video_params, output_container,
                                         dict['task_id'],
                                         dict.get('parts', 1))

    @classmethod
    def _assert_codec_container_support(cls, audio_codec, video_codec,
                                        output_container):
        if audio_codec not in output_container.get_supported_audio_codecs():
            raise TranscodingTaskBuilderExcpetion(
                'Container {} does not support {}'.format(output_container,
                                                          audio_codec))

        if video_codec not in output_container.get_supported_video_codecs():
            raise TranscodingTaskBuilderExcpetion(
                'Container {} does not support {}'.format(output_container,
                                                          video_codec))

    @classmethod
    def build_minimal_definition(cls, task_type: CoreTaskTypeInfo,
                                 dict: Dict[str, Any]):
        return cls.build_full_definition(task_type, dict)

    @classmethod
    @HandleError(ValueError, apps.transcoding.common.not_valid_json)
    @HandleError(IOError, apps.transcoding.common.file_io_error)
    def _get_presets(cls, path: str) -> Dict[str, Any]:
        # FIXME get metadata by ffmpeg docker container
        # with open(path) as f:
        # return json.load(f)
        return {}

    @classmethod
    def _get_required_field(cls, dict, key : str) -> str:
        v = dict.get(key)
        if not v:
            raise TranscodingTaskBuilderExcpetion(
                'Field {} is required in the task definition'.format(key))
        return v


class TranscodingTaskOptions(Options):
    pass


class TranscodingTaskBuilderExcpetion(Exception):
    pass

