import functools
import logging
import subprocess

from typing import List

from golem.core.common import is_linux, unix_pipe


logger = logging.getLogger(__name__)


MIN_DRIVER_VERSION = 396.0


@functools.lru_cache(5)
def is_supported(*_) -> bool:
    try:
        return _is_supported()
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("NVGPU Docker environment is not supported: %r", exc)
    return False


def get_devices(*_) -> List[int]:
    # Fixme: add configuration
    return [0]


def get_unified_memory_enabled() -> bool:
    # Fixme: add configuration
    return True


def _is_supported(*_) -> bool:
    # soft fail section
    if not is_linux():
        return False

    dev_nvidia = unix_pipe(['lspci'], ['grep', '-i', 'nvidia'])
    if not dev_nvidia:
        return False

    # hard fail section
    mod_nouveau = unix_pipe(['lsmod'], ['grep', '-i', 'nouveau'])
    if mod_nouveau:
        raise RuntimeError('nouveau driver is not compatible with '
                           'nvidia-docker')

    # We will try to use the Unified Memory kernel module to create the devices.
    # Unified Memory is not available on pre-Pascal architectures.
    if not _modprobe(unified_memory=get_unified_memory_enabled()):
        _modprobe(unified_memory=False)
        logger.debug('Unified memory is not supported')

    _assert_driver_version()

    dev_nvidia_ctl = unix_pipe(['ls', '/dev'], ['grep', '-i', 'nvidiactl'])
    if not dev_nvidia_ctl:
        raise RuntimeError('nvidiactl device not found')

    mod_nvidia_uvm = unix_pipe(['lsmod'], ['grep', '-i', 'nvidia_uvm'])
    if not mod_nvidia_uvm:
        raise RuntimeError('nvidia_uvm kernel module was not loaded')

    dev_nvidia_uvm = unix_pipe(['ls', '/dev'], ['grep', '-i', 'nvidia-uvm'])
    if not dev_nvidia_uvm:
        raise RuntimeError('nvidia-uvm device not found')

    return True


def _modprobe(unified_memory: bool) -> bool:

    command = ['nvidia-modprobe'] + ['-c={}'.format(d) for d in get_devices()]
    if unified_memory:
        command.append('-u')

    try:
        subprocess.check_call(command)
    except subprocess.CalledProcessError as exc:
        if unified_memory and exc.returncode == 1:
            return False
        raise RuntimeError(f'{command} failed')
    return True


def _assert_driver_version() -> None:

    try:
        output = unix_pipe(['modinfo', 'nvidia'], ['grep', '^version'])
        version = float(output.split(' ')[-1])
    except (IndexError, TypeError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f'Unable to read NVIDIA driver version: {str(exc)}')

    if version < MIN_DRIVER_VERSION:
        raise RuntimeError(f'The installed NVIDIA driver is too old; '
                           f'At least {MIN_DRIVER_VERSION} is required.')

    logger.debug("NVIDIA driver version: %s", version)
