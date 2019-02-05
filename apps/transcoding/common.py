import logging
from enum import Enum

from golem.core.common import HandleValueError

logger = logging.getLogger(__name__)


def not_valid_json(exception_type, path: str):
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
    H_264 = 'LIBX264'
    MPEG_2 = 'MPEG-2'
    MPEG_4 = 'MPEG-4'
    MPEG_4_Part_2 = 'MPEG-4 PART 2'
    VP6 = 'VP6'

    @staticmethod
    @HandleValueError(unsupported)
    def from_name(name: str) -> 'VideoCodec':
        return VideoCodec(name.upper())


class AudioCodec(Enum):
    MP3 = 'MP3'
    AAC = 'AAC'
    PCM = 'PCM'

    @staticmethod
    @HandleValueError(unsupported)
    def from_name(name: str) -> 'AudioCodec':
        return AudioCodec(name.upper())


class Container(Enum):
    MP4 = 'mp4'
    AVI = 'avi'
    MKV = 'mkv'

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
    Container.AVI: ALL_SUPPORTED_CODECS,
    Container.MKV: ALL_SUPPORTED_CODECS,
    Container.MP4: ([VideoCodec.H_264, VideoCodec.MPEG_4_Part_2,
                     VideoCodec.MPEG_2],
                    [AudioCodec.AAC, AudioCodec.MP3])
}


def is_type_of(type):
    def f(obj):
        return isinstance(obj, type)
    return f


class ffmpegException(Exception):
    pass


class TranscodingException(Exception):
    pass


class TranscodingTaskBuilderException(Exception):
    pass
