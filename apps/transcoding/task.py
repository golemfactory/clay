import json
from multiprocessing import Lock
from typing import Any, Dict, Tuple, Optional

import golem_messages

from apps.core.task.coretask import CoreTask, CoreTaskBuilder, CoreTaskTypeInfo
from apps.core.task.coretaskstate import Options, TaskDefinition
from apps.transcoding import common
from apps.transcoding.common import AudioCodec, VideoCodec, Container
from apps.transcoding.ffmpeg.utils import StreamOperator
from golem.core.common import HandleError
from golem.resource.dirmanager import DirManager
from golem.task.taskstate import SubtaskStatus


class TranscodingTask(CoreTask):

    def __init__(self, task_definition, **kwargs):
        super(TranscodingTask, self).__init__(task_definition=task_definition,
                                              **kwargs)
        self.lock = Lock()


    def initialize(self, dir_manager: DirManager):
        super(TranscodingTask, self).initialize(dir_manager)

        if len(self.task_resources) == 0:
            raise TranscodingException('There is no specified resources')
        stream_operator = StreamOperator()
        chunks = stream_operator.split_video(
            self.task_resources[0], self.task_definition['parts'], dir_manager,
            self.task_definition['task_id'])
        self.task_resources = chunks
        self.pending_subtasks = len(chunks)

    def _get_next_task(self):
        with self.lock:
            subtasks = self.subtasks_given.values()
            subtasks = filter(lambda sub: sub['status'] in [
                SubtaskStatus.failure, SubtaskStatus.restarted], subtasks)
            # Jakie statusy trzeba restartowac
            failed_subtask = next(iter(subtasks), None)
            if failed_subtask:
                assert self.num_failed_subtasks > 0
                failed_subtask['status'] = SubtaskStatus.resent
                self.num_failed_subtasks -= 1
                return failed_subtask

            return failed_subtask['sub_id']


            if self.last_task != self.total_tasks:
                self.last_task += 1
                start_task = self.last_task
                return start_task
            else:
                    if sub['status'] \
                            in [SubtaskStatus.failure, SubtaskStatus.restarted]:

                        start_task = sub['start_task']
                        self.num_failed_subtasks -= 1
                        return start_task
            return None



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

    def __init__(self, input_stream_path, audio_params, video_params):
        super().__init__()
        self.input_stream_path = input_stream_path
        self.audio_params = audio_params
        self.video_params = video_params


class TranscodingTaskBuilder(CoreTaskBuilder):
    # jako property
    SUPPORTED_FILE_TYPES = []
    SUPPORTED_VIDEO_CODECS = []
    SUPPORTED_AUDIO_CODECS = []

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

        task_def = TranscodingTaskDefinition(input_stream_path, audio_params,
                                             video_params)

        task_def.video_params.target_encoding = dict['target_encoding']
        return task_def

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
    @HandleError(ValueError, common.not_valid_json)
    @HandleError(IOError, common.file_io_error)
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


class TranscodingException(Exception):
    pass


class TranscodingTaskBuilderExcpetion(Exception):
    pass
