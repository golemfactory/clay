import os

from cpuinfo import get_cpu_info

from golem.core.common import get_golem_path, is_linux, is_windows
from golem.core.windows import run_powershell
from golem.rpc import utils as rpc_utils

WIN_SCRIPT_PATH = os.path.join(
    get_golem_path(),
    'scripts',
    'virtualization',
    'get-virtualization-state.ps1'
)


@rpc_utils.expose('env.hw.virtualization')
def is_virtualization_enabled() -> bool:
    """ Checks if hardware virtualization is available on this machine.
    Currently, this check is limited to Intel CPUs (VT and VT-x support).
    :return bool: True if virtualization is available or the OS is Linux.
    On Windows, we additionally check if the feature is enabled in firmware.
    """
    if is_linux():
        # Virtualization support is not required to run Golem on Linux.
        return True
    elif is_windows():
        return _check_vt_windows()

    return _check_vt_unix()


def _check_vt_unix() -> bool:
    cpu_flags: list = get_cpu_info()['flags']
    return 'vmx' in cpu_flags


def _check_vt_windows() -> bool:
    virtualization_state = run_powershell(script=WIN_SCRIPT_PATH)
    return virtualization_state == 'True'

