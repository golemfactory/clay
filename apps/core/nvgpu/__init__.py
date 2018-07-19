import subprocess
from typing import List

from golem.core.common import is_linux


def is_supported(*_) -> bool:
    try:
        return _is_supported()
    except Exception as exc:  # pylint: disable=broad-except
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("NVGPU Docker environment is not supported: %r", exc)
        return False


def _is_supported(*_) -> bool:
    # soft fail section
    if not is_linux():
        return False

    dev_nvidia = _pipe(['lspci'], ['grep', '-i', 'nvidia'])
    if not dev_nvidia:
        return False

    # hard fail section
    mod_nouveau = _pipe(['lsmod'], ['grep', '-i', 'nouveau'])
    if mod_nouveau:
        raise RuntimeError('nouveau driver is not compatible with '
                           'nvidia-docker')

    mod_nvidia = _pipe(['lsmod'], ['grep', '-i', 'nvidia'])
    if not mod_nvidia:
        raise RuntimeError('nvidia kernel module not loaded')

    mod_nvidia_uvm = _pipe(['lsmod'], ['grep', '-i', 'nvidia_uvm'])
    if not mod_nvidia_uvm:
        raise RuntimeError('nvidia_uvm kernel module was not loaded')

    dev_nvidia_0 = _pipe(['ls', '-l', '/dev'], ['grep', '-i', 'nvidia0'])
    if not dev_nvidia_0:
        raise RuntimeError('nvidia0 device not found')

    dev_nvidia_uvm = _pipe(['ls', '-l', '/dev'], ['grep', '-i', 'nvidia-uvm'])
    if not dev_nvidia_uvm:
        raise RuntimeError('nvidia-uvm device not found')

    dev_nvidia_ctl = _pipe(['ls', '-l', '/dev'], ['grep', '-i', 'nvidiactl'])
    if not dev_nvidia_ctl:
        raise RuntimeError('nvidiactl device not found')

    return True


def _pipe(cmd: List[str], pipe: List[str]):
    proc_cmd = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE)
    proc_pipe = subprocess.Popen(pipe,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 stdin=proc_cmd.stdout)
    proc_cmd.stdout.close()
    stdout, _ = proc_pipe.communicate()
    return stdout.strip()
