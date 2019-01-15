import locale
import re
import subprocess

from cpuinfo import get_cpu_info

from golem.core.common import is_windows
from golem.rpc import utils as rpc_utils


@rpc_utils.expose('env.hw.virtualization')
def is_virtualization_enabled() -> bool:
    """ Checks if hardware virtualization is available on this machine.
    Currently, this check is limited to Intel CPUs (VT and VT-x support).
    :return bool: True if virtualization is available. On Windows, we also check
    if the feature is enabled in firmware.
    """
    if is_windows():
        return __check_vt_windows()

    return __check_vt_unix()


def __check_vt_unix() -> bool:
    cpu_flags: list = get_cpu_info()['flags']
    return 'vmx' in cpu_flags


def __check_vt_windows() -> bool:
    sys_info: subprocess.CompletedProcess = \
        subprocess.run('systeminfo', check=True, stdout=subprocess.PIPE)

    # https://stackoverflow.com/a/9228117
    try:
        output = sys_info.stdout.decode(locale.getpreferredencoding())
    except ValueError:
        output = sys_info.stdout.decode()

    key_vt_supported = 'VM Monitor Mode Extensions'
    key_vt_enabled = 'Virtualization Enabled In Firmware'

    return __check_systeminfo_field(key_vt_supported, output) and \
        __check_systeminfo_field(key_vt_enabled, output)


def __check_systeminfo_field(key: str, command_output: str) -> bool:
    pattern = re.compile(f'(.*){key}:(\\s+)(\\w*)')
    match = pattern.search(command_output)

    return match and match.group(match.lastindex) == 'Yes'
