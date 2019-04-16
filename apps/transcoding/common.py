import logging
from typing import Type

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
    logger.warning('%s is not supported', name)
    raise TranscodingTaskBuilderException('{} is not supported'.format(name))


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


class VideoCodecNotSupportedByContainer(TranscodingTaskBuilderException):
    pass


class AudioCodecNotSupportedByContainer(TranscodingTaskBuilderException):
    pass
