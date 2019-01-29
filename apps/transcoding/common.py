import logging
from enum import Enum

from golem.core.common import HandleKeyError


logger = logging.getLogger(__name__)


def not_valid_json(exception_type, path: str): # TYPY
    msg = 'File {} is not valid JSON'.format(path)
    logger.warning(msg)
    raise TranscodingException(msg)


def file_io_error(path: str):
    msg = 'I/O error occurred during access to file {}'.format(path)
    logger.warning(msg)
    raise TranscodingException(msg)


def unsupported(name: str):
    logger.warning('{} is not supported'.format(name))
    raise TranscodingException('{} is not supported'.format(name))


class VideoCodec(Enum):
    H_264 = 'libx264'
    MPEG_2 = 'MPEG-2'
    MPEG_4 = 'MPEG-4'
    MPEG_4_Part_2 = 'MPEG-4 Part 2'

    @staticmethod
    @HandleKeyError(unsupported)
    def from_name(name: str) -> 'VideoCodec':
        return VideoCodec(name.upper())


class AudioCodec(Enum):
    MP3 = 'MP3'
    AAC = 'AAC'

    @staticmethod
    @HandleKeyError(unsupported)
    def from_name(name: str) -> 'AudioCodec':
        return AudioCodec(name.lower())


class Container(Enum):
    MP4 = 'mp4'
    AVI = 'avi'
    MKV = 'mkv'

    @staticmethod
    @HandleKeyError(unsupported)
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



class ffmpegException(Exception):
    pass


class TranscodingException(Exception):
    pass
