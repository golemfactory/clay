import locale
import re
import subprocess

from golem.core.common import is_windows, is_osx

win_key_vt_supported = 'VM Monitor Mode Extensions'
win_key_vt_enabled = 'Virtualization Enabled In Firmware'


def is_vt_enabled() -> bool:
    if is_windows():
        sys_info: subprocess.CompletedProcess = \
            subprocess.run('systeminfo', check=True, stdout=subprocess.PIPE)
        output: str = None

        # https://stackoverflow.com/a/9228117
        try:
            output = sys_info.stdout.decode(locale.getpreferredencoding())
        except ValueError:
            output = sys_info.stdout.decode()

        return __check_systeminfo_field(win_key_vt_supported, output) and \
            __check_systeminfo_field(win_key_vt_enabled, output)


def __check_systeminfo_field(key: str, command_output: str) -> bool:
    pattern = re.compile(f'(.*){key}:(\\s+)(\\w*)')
    match = pattern.search(command_output)

    return match and match.group(match.lastindex) == 'Yes'
