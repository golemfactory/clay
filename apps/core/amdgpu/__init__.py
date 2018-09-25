import functools
import logging
import os
from typing import List

from golem.core.common import unix_pipe, is_linux

logger = logging.getLogger(__name__)


@functools.lru_cache(5)
def is_supported(*_) -> bool:
    try:
        return _is_supported()
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("AMD Docker environment is not supported: %r", exc)
    return False


def get_devices(*_) -> List[int]:
    # Fixme: add configuration
    return [0]


def _is_supported() -> bool:

    if not is_linux():
        return False

    if not os.path.exists('/etc/OpenCL'):
        raise RuntimeError('/etc/OpenCL not found')

    if not os.path.exists('/opt/amdgpu/lib/x86_64-linux-gnu'):
        raise RuntimeError('amdgpu libraries not found')

    mod_amdgpu = unix_pipe(['lsmod'], ['grep', '-i', 'amdgpu'])
    if not mod_amdgpu:
        raise RuntimeError('amdgpu kernel module not loaded')

    dev_dri = unix_pipe(['ls', '/dev'], ['grep', '-i', 'dri'])
    if not dev_dri:
        raise RuntimeError('dri device not found')

    return True
