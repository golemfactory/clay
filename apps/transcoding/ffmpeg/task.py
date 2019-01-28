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
# Czym sie rozni minimal definition od full?
# poprawic impoorty
# Co to są property?
# Obsluga bledow
# LOGI


class ffmpegTaskTypeInfo(CoreTaskTypeInfo):
    def __init__(self):
        super().__init__('FFMPEG', TranscodingTaskDefinition,
                         TranscodingTaskOptions, TranscodingTaskBuilder)


class ffmpegTask(TranscodingTask):
    ENVIRONMENT_CLASS = ffmpegEnvironment

    def _get_extra_data(self, subtask_num):
        assert subtask_num < len(self.task_resources)

        stream_path = os.path.relpath(self.task_resources[subtask_num],
                                      self._get_resources_root_dir())
        stream_path = DockerJob.get_absolute_resource_path(stream_path)
        output_stream_path = str(pathlib.Path(stream_path).with_suffix(
            '.{}'.format(self.task_definition.output_container)))

        resolution = self.task_definition.video_params.resolution
        filename = os.path.splitext(os.path.basename(stream_path))[0]
        os.path.join(os.path.dirname(os.path.abspath(stream_path)), filename)
        extra_data = {
            'track': stream_path,
            'targs': {
                'video': {
                    'codec': self.task_definition.video_params.codec,
                    'bitrate': self.task_definition.video_params.bitrate
                    },
                'audio': {
                    'codec': self.task_definition.audio_params.codec,
                    'bitrate': self.task_definition.audio_params.bitrate
                },
                'resolution': [resolution[0], resolution[1]],
                'frame_rate': self.task_definition.video_params.frame_rate
            },
            'output_stream': output_stream_path,
            'use_playlist': self.task_definition.use_playlist,
            'command': Commands.TRANSCODE,
            'script_filepath': FFMPEG_BASE_SCRIPT
        }

        return extra_data


class ffmpegDefaults(TaskDefaults):
    """ Suggested default values for Rendering tasks"""
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


