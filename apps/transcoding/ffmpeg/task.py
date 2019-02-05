import logging
import os
import pathlib

from apps.core.task.coretask import CoreTaskTypeInfo
from apps.core.task.coretaskstate import TaskDefaults
from apps.transcoding.common import Container, VideoCodec, AudioCodec
from apps.transcoding.ffmpeg.environment import ffmpegEnvironment
from apps.transcoding.ffmpeg.utils import Commands, FFMPEG_BASE_SCRIPT
from apps.transcoding.task import TranscodingTaskOptions, \
    TranscodingTaskBuilder, TranscodingTaskDefinition, TranscodingTask
from golem.docker.job import DockerJob


# TODO:
# Czy typować? Co robia inni (A?)
# Co to są property?

from golem.verificator.ffmpeg_verifier import ffmpegVerifier

logger = logging.getLogger(__name__)


class ffmpegTaskTypeInfo(CoreTaskTypeInfo):
    def __init__(self):
        super().__init__('FFMPEG', TranscodingTaskDefinition,
                         ffmpegTaskOptions, ffmpegTaskBuilder)


class ffmpegTask(TranscodingTask):
    ENVIRONMENT_CLASS = ffmpegEnvironment
    VERIFIER_CLASS = ffmpegVerifier

    def _get_extra_data(self, subtask_num):
        transcoding_options = self.task_definition.options
        video_params = transcoding_options.video_params
        audio_params = transcoding_options.audio_params
        if subtask_num >= len(self.task_resources):
            raise AssertionError('Requested number subtask {} is greater than '
                                 'number of resources [size={}]'
                                 .format(subtask_num, len(self.task_resources)))

        stream_path = os.path.relpath(self.task_resources[subtask_num],
                                      self._get_resources_root_dir())
        stream_path = DockerJob.get_absolute_resource_path(stream_path)
        filename = os.path.basename(stream_path)

        output_stream_path = pathlib.Path(os.path.join(DockerJob.OUTPUT_DIR,
                                                       filename))
        output_stream_path = str(output_stream_path.with_suffix(
            '.{}'.format(transcoding_options.output_container.value)))

        resolution = video_params.resolution
        resolution = [resolution[0], resolution[1]] if resolution else None
        vc = video_params.codec.value if video_params.codec else None
        ac = audio_params.codec.value if audio_params.codec else None
        extra_data = {
            'track': stream_path,
            'targs': {
                'video': {
                    'codec': vc,
                    'bitrate': video_params.bitrate
                    },
                'audio': {
                    'codec': ac,
                    'bitrate': audio_params.bitrate
                },
                'resolution': resolution,
                'frame_rate': video_params.frame_rate
            },
            'output_stream': output_stream_path,
            'use_playlist': transcoding_options.use_playlist,
            'command': Commands.TRANSCODE.value[0],
            'script_filepath': FFMPEG_BASE_SCRIPT
        }
        return self._clear_none_values(extra_data)

    def _clear_none_values(self, d):
        return {k: v if not isinstance(v, dict) else self._clear_none_values(v)
                for k, v in d.items() if v is not None}


class ffmpegDefaults(TaskDefaults):
    def __init__(self):
        super(ffmpegDefaults, self).__init__()


class ffmpegTaskBuilder(TranscodingTaskBuilder):
    SUPPORTED_FILE_TYPES = [Container.MKV, Container.AVI,
                            Container.MP4]
    SUPPORTED_VIDEO_CODECS = [VideoCodec.MPEG_2, VideoCodec.H_264]
    SUPPORTED_AUDIO_CODECS = [AudioCodec.MP3, AudioCodec.AAC]
    TASK_CLASS = ffmpegTask
    DEFAULTS = ffmpegDefaults


class ffmpegTaskDefinition(TranscodingTaskDefinition):
    pass


class ffmpegTaskOptions(TranscodingTaskOptions):
    def __init__(self):
        super(ffmpegTaskOptions, self).__init__()
        self.environment = ffmpegEnvironment()
