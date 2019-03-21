import os

from cpuinfo import get_cpu_info

from golem.core.common import get_golem_path, is_linux, is_windows
from golem.core.windows import run_powershell
from golem.rpc import utils as rpc_utils

SCRIPTS_PATH = os.path.join(
    get_golem_path(),
    'scripts',
    'virtualization'
)

VIRTUALIZATION_SCRIPT_NAME = 'get-virtualization-state.ps1'
HYPERV_SCRIPT_NAME = 'get-hyperv-state.ps1'


@rpc_utils.expose('env.hw.virtualization')
def is_virtualization_satisfied() -> bool:
    """ Checks if hardware virtualization is available on this machine.
    If hardware virtualization is not required to run Golem (e.g. on Linux),
    the actual check is skipped. Currently, this function is limited to Intel
    CPUs (VT and VT-x support).
    :return bool: True if virtualization is available or is not required.
    On Windows, we additionally check if the feature is enabled in firmware.
    """
    if is_linux():
        return True
    elif is_windows():
        return _check_vt_windows()

    return _check_vt_unix()


def _check_vt_unix() -> bool:
    cpu_flags: list = get_cpu_info()['flags']
    return 'vmx' in cpu_flags


def _check_vt_windows() -> bool:
    hyperv_state = run_powershell(
        script=os.path.join(SCRIPTS_PATH, HYPERV_SCRIPT_NAME)
    )
    if hyperv_state == 'True':
        return True

    virtualization_state = run_powershell(
        script=os.path.join(SCRIPTS_PATH, VIRTUALIZATION_SCRIPT_NAME)
    )
    return virtualization_state == 'True'
