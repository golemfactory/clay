import subprocess
from typing import List

from golem.core.common import is_linux


def is_supported(*_) -> bool:
    try:
        return _is_supported()
    except Exception as exc:  # pylint: disable=broad-except
        import logging
        logger = logging.getLogger(__name__)
        logger.debug("Error executing is_supported: %r", exc)
        return False


def _is_supported(*_) -> bool:
    if not is_linux():
        return False

    dev_nvidia = _pipe(['lspci'], ['grep', '-i', 'nvidia'])
    if not dev_nvidia:
        return False

    mod_nouveau = _pipe(['lsmod'], ['grep', '-i', 'nouveau'])
    if mod_nouveau:
        return False

    mod_nvidia = _pipe(['lsmod'], ['grep', '-i', 'nvidia'])
    if not mod_nvidia:
        return False

    return True


def _pipe(cmd: List[str], pipe: List[str]):
    proc_cmd = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE)
    proc_pipe = subprocess.Popen(pipe,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 stdin=proc_cmd.stdout)
    proc_cmd.stdout.close()
    stdout, stderr = proc_pipe.communicate()
    return stdout.strip()
