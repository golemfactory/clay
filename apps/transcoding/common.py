import logging
from enum import Enum
from typing import Type

from golem.core.common import HandleValueError

logger = logging.getLogger(__name__)


def not_valid_json(exception_type: Type[Exception], path: str):
    msg = 'File {} is not valid JSON'.format(path)
    logger.warning(msg)
    raise exception_type(msg)


def file_io_error(path: str):
    msg = 'I/O error occurred during access to file {}'.format(path)
    logger.warning(msg)
    raise TranscodingException(msg)


def unsupported(name: str):
    logger.warning('{} is not supported'.format(name))
    raise TranscodingTaskBuilderException('{} is not supported'.format(name))


class VideoCodec(Enum):
    H_264 = 'h264'
    H_265 = 'h265'
    HEVC = 'HEVC'
    MPEG_1 = 'mpeg1video'
    MPEG_2 = 'mpeg2video'
    MPEG_4 = 'mpeg4'

    @staticmethod
    @HandleValueError(unsupported)
    def from_name(name: str) -> 'VideoCodec':
        return VideoCodec(name)


class AudioCodec(Enum):
    AAC = 'aac'
    MP3 = 'mp3'

    @staticmethod
    @HandleValueError(unsupported)
    def from_name(name: str) -> 'AudioCodec':
        return AudioCodec(name)


class Container(Enum):
    MP4 = 'mp4'
    AVI = 'avi'
    MKV = 'mkv'
    TS = 'ts'

    @staticmethod
    @HandleValueError(unsupported)
    def from_name(name: str) -> 'Container':
        return Container(name.lower())

    def get_supported_video_codecs(self):
        return CONTAINER_SUPPORTED_CODECS[self][0]

    def get_supported_audio_codecs(self):
        return CONTAINER_SUPPORTED_CODECS[self][1]


ALL_SUPPORTED_CODECS = ([c for c in VideoCodec], [c for c in AudioCodec])
CONTAINER_SUPPORTED_CODECS = {
    Container.AVI: ([VideoCodec.MPEG_4], [AudioCodec.AAC]),
    Container.MKV: ([], []),
    Container.MP4: ([VideoCodec.H_264, VideoCodec.H_265, VideoCodec.HEVC,
                     VideoCodec.MPEG_1, VideoCodec.MPEG_2, VideoCodec.MPEG_4],
                    [AudioCodec.AAC, AudioCodec.MP3]),
}


def is_type_of(t: Type):
    def f(obj):
        return isinstance(obj, t)

    return f


class ffmpegException(Exception):
    pass


class TranscodingException(Exception):
    pass


class TranscodingTaskBuilderException(Exception):
    pass
