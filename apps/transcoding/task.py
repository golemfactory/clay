import abc
import logging
import os
from shutil import move
from threading import Lock
from typing import Any, Dict, List, Tuple, Optional, Union

import golem_messages.message

import ffmpeg_tools.validation as validation
import ffmpeg_tools.meta as meta
from ffmpeg_tools.codecs import VideoCodec, AudioCodec
from ffmpeg_tools.formats import Container

import apps.transcoding.common
from apps.core.task.coretask import CoreTask, CoreTaskBuilder, CoreTaskTypeInfo
from apps.core.task.coretaskstate import Options, TaskDefinition
from apps.transcoding.common import TranscodingException
from apps.transcoding.ffmpeg.utils import StreamOperator
from golem.core.common import HandleError, timeout_to_deadline
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import Task
from golem.task.taskstate import SubtaskStatus
from .common import is_type_of, TranscodingTaskBuilderException, \
    AudioCodecNotSupportedByContainer, VideoCodecNotSupportedByContainer


logger = logging.getLogger(__name__)


class TranscodingTaskOptions(Options):
    class AudioParams:
        def __init__(self,
                     codec: Optional[AudioCodec] = None,
                     bitrate: Optional[str] = None) -> None:
            self.codec = codec
            self.bitrate = bitrate

    class VideoParams:
        def __init__(self,
                     codec: Optional[VideoCodec] = None,
                     bitrate: Optional[str] = None,
                     frame_rate: Optional[Union[int, str]] = None,
                     resolution: Optional[Tuple[int, int]] = None) -> None:
            self.codec = codec
            self.bitrate = bitrate
            self.frame_rate = frame_rate
            self.resolution = resolution

    def __init__(self):
        super().__init__()
        self.video_params = TranscodingTaskOptions.VideoParams()
        self.audio_params = TranscodingTaskOptions.AudioParams()
        self.input_stream_path = None
        self.output_container = None


class TranscodingTaskDefinition(TaskDefinition):
    def __init__(self):
        super(TranscodingTaskDefinition, self).__init__()
        self.options = TranscodingTaskOptions()


class TranscodingTask(CoreTask):  # pylint: disable=too-many-instance-attributes
    def __init__(self, task_definition: TranscodingTaskDefinition, **kwargs) \
            -> None:
        super(TranscodingTask, self).__init__(task_definition=task_definition,
                                              **kwargs)
        self.task_definition = task_definition
        self.lock = Lock()
        self.chunks: List[str] = list()
        self.collected_files: List[str] = list()
        self.task_dir = ""

    def __getstate__(self):
        state = super(TranscodingTask, self).__getstate__()
        del state['lock']
        return state

    def __setstate__(self, state):
        super(TranscodingTask, self).__setstate__(state)
        self.lock = Lock()

    def initialize(self, dir_manager: DirManager):
        super(TranscodingTask, self).initialize(dir_manager)

        logger.debug('Initialization of FFmpegTask')

        task_id = self.task_definition.task_id
        task_output_dir = dir_manager.get_task_output_dir(task_id)

        # results from providers are collected in tmp
        self.task_dir = dir_manager.get_task_temporary_dir(task_id)
        if not self.task_resources:
            raise TranscodingException('There is no specified resources')

        input_file = self.task_resources[0]

        stream_operator = StreamOperator()
        chunks, video_metadata = stream_operator.\
            extract_video_streams_and_split(
                input_file,
                self.task_definition.subtasks_count,
                dir_manager,
                task_id)

        if len(chunks) < self.total_tasks:
            logger.warning('%d subtasks was requested but video splitting '
                           'process resulted in %d chunks.',
                           self.total_tasks,
                           len(chunks))

        streams = list(map(lambda x: x if os.path.isabs(x) else os.path
                           .join(task_output_dir, x), chunks))

        self.task_resources = streams
        self.chunks = streams
        self.total_tasks = len(chunks)
        self.task_definition.subtasks_count = len(chunks)

        try:
            validation.validate_video(video_metadata)

            src_params = meta.create_params(
                meta.get_format(video_metadata),
                meta.get_resolution(video_metadata),
                meta.get_video_codec(video_metadata),
                meta.get_audio_codec(video_metadata),
                meta.get_frame_rate(video_metadata))

            # Get parameters for example subtasks. All subtasks should have
            # the same conversion parameters which we check here, so it doesn't
            # matter which we choose.
            dst_params = self._get_extra_data(0)["targs"]

            validation.validate_transcoding_params(
                src_params,
                dst_params,
                video_metadata
            )

        except validation.InvalidVideo as e:
            logger.error(e.response_message)
            raise e

    def accept_results(self, subtask_id, result_files):
        with self.lock:
            super(TranscodingTask, self).accept_results(subtask_id,
                                                        result_files)
            self._collect_results(result_files)

            self.num_tasks_received += 1

            logger.info("Task %s - transcoded %d of %d chunks",
                        self.task_definition.task_id,
                        self.num_tasks_received,
                        self.total_tasks)

            if self.num_tasks_received == self.total_tasks:
                self._merge_video()

    def _collect_results(self, results):
        self.collected_files.extend(results)

    def _merge_video(self):
        logger.info('Merging video [task_id = %s]',
                    self.task_definition.task_id)

        output_basename = os.path.basename(self.task_definition.output_file)

        assert len(self.task_definition.resources) == 1, \
            "Assumption: input file is the only resource in a transcoding task"
        input_file = next(iter(self.task_definition.resources))

        stream_operator = StreamOperator()
        output_file = stream_operator.merge_and_replace_video_streams(
            input_file,
            self.collected_files,
            output_basename,
            self.task_dir,
            self.task_definition.options.output_container,
        )

        # Move result to desired location.
        os.makedirs(os.path.dirname(self.task_definition.output_file),
                    exist_ok=True)
        move(output_file, self.task_definition.output_file)

        logger.info("Video merged successfully [task_id = %s]",
                    self.task_definition.task_id)

        return True

    def _get_next_subtask(self):
        logger.debug('Getting next task [type=trancoding, task_id=%s]',
                     self.task_definition.task_id)
        subtasks = self.subtasks_given.values()
        subtasks = filter(lambda sub: sub['status'] in [
            SubtaskStatus.failure, SubtaskStatus.restarted], subtasks)

        failed_subtask = next(iter(subtasks), None)
        if failed_subtask:
            logger.debug('Subtask %s was failed, so let resent it',
                         failed_subtask['subtask_id'])
            failed_subtask['status'] = SubtaskStatus.resent
            self.num_failed_subtasks -= 1
            return failed_subtask['subtask_num']

        assert self.last_task < self.total_tasks
        curr = self.last_task + 1
        self.last_task = curr
        return curr - 1

    def query_extra_data(self, perf_index: float, node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> Task.ExtraData:
        with self.lock:
            sid = self.create_subtask_id()

            subtask_num = self._get_next_subtask()
            subtask: Dict[str, Any] = {}
            transcoding_params = self._get_extra_data(subtask_num)
            subtask['perf'] = perf_index
            subtask['node_id'] = node_id
            subtask['subtask_id'] = sid
            subtask['transcoding_params'] = transcoding_params
            subtask['subtask_num'] = subtask_num
            subtask['status'] = SubtaskStatus.starting

            self.subtasks_given[sid] = subtask

            return Task.ExtraData(ctd=self._get_task_computing_definition(
                sid,
                transcoding_params,
                perf_index,
                resources=[self.chunks[subtask_num]]))

    def query_extra_data_for_test_task(
            self) -> golem_messages.message.ComputeTaskDef:
        # TODO
        pass

    def _get_task_computing_definition(self,
                                       sid,
                                       transcoding_params,
                                       perf_idx,
                                       resources):
        ctd = golem_messages.message.ComputeTaskDef()
        ctd['task_id'] = self.header.task_id
        ctd['subtask_id'] = sid
        ctd['extra_data'] = transcoding_params
        ctd['performance'] = perf_idx
        ctd['docker_images'] = [di.to_dict() for di in self.docker_images]
        ctd['deadline'] = min(timeout_to_deadline(self.header.subtask_timeout),
                              self.header.deadline)
        ctd['resources'] = resources
        return ctd

    @abc.abstractmethod
    def _get_extra_data(self, subtask_num):
        pass


class TranscodingTaskBuilder(CoreTaskBuilder):
    SUPPORTED_FILE_TYPES: List[Container] = []
    SUPPORTED_VIDEO_CODECS: List[VideoCodec] = []
    SUPPORTED_AUDIO_CODECS: List[AudioCodec] = []

    @classmethod
    def build_full_definition(cls, task_type: CoreTaskTypeInfo,
                              dictionary: Dict[str, Any]):
        task_def = super().build_full_definition(task_type, dictionary)

        try:
            presets = cls._get_presets(task_def.options.input_stream_path)
            options = dictionary.get('options', {})
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
            task_def.options.name = dictionary.get('name', '')

            logger.debug(
                'Transcoding task definition has been built [definition=%s]',
                task_def.__dict__)

            return task_def

        except validation.InvalidVideo as e:
            logger.warning(e.response_message)
            raise e

    @classmethod
    def _assert_codec_container_support(cls, audio_codec, video_codec,
                                        output_container):
        if audio_codec and \
                not output_container.is_supported_audio_codec(audio_codec):
            raise AudioCodecNotSupportedByContainer(
                'Container {} does not support {}'.format(
                    output_container.value, audio_codec.value))

        if video_codec and \
                not output_container.is_supported_video_codec(video_codec):
            raise VideoCodecNotSupportedByContainer(
                'Container {} does not support {}'.format(
                    output_container.value, video_codec.value))

    @classmethod
    def build_minimal_definition(cls, task_type: CoreTaskTypeInfo,
                                 dictionary: Dict[str, Any]):
        df = super(TranscodingTaskBuilder, cls).build_minimal_definition(
            task_type, dictionary)
        stream = cls._get_required_field(
            dictionary,
            'resources',
            is_type_of(list),
        )[0]
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
    def _get_required_field(cls,
                            dictionary,
                            key: str,
                            validator=lambda _: True) -> Any:
        v = dictionary.get(key)
        if not v or not validator(v):
            raise TranscodingTaskBuilderException(
                'Field {} is required in the task definition'.format(key))
        return v

    @classmethod
    def get_output_path(cls, dictionary: dict, definition):

        # Override default output_file path constructed in parent class.
        # We don't want to append timestamp to directory.
        options = cls._get_required_field(dictionary, 'options',
                                          is_type_of(dict))

        container = options.get('container', cls._get_presets(
            definition.options.input_stream_path))
        alternative_name = '{}.{}'.format(definition.name, container)

        filename = options.get("output_filename", alternative_name)
        return os.path.join(options['output_path'], filename)
