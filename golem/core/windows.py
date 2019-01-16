import subprocess
from typing import List, Optional

DEFAULT_SCRIPT_TIMEOUT = 5  # seconds


def run_powershell(
        script: Optional[str] = None,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        use_profile: Optional[bool] = False,
        timeout: int = DEFAULT_SCRIPT_TIMEOUT
) -> str:
    """
    Runs a PowerShell script or command and returns its output in UTF8.
    :param script: path of PowerShell script to execute
    :param command: PowerShell command to execute
    :param args: optional extra arguments
    :param use_profile: when set to True, PowerShell will first load all profile scripts present on the machine before
    running the actual command or script.
    :param timeout: timeout for the script or command, in seconds
    """
    cmd = ['powershell.exe']

    if not use_profile:
        cmd += ['-NoProfile']

    if script and not command:
        cmd += [
            '-ExecutionPolicy', 'RemoteSigned',
            '-File', script
        ]
    elif command and not script:
        cmd += [
            '-Command', command
        ]
    else:
        raise ValueError("Exactly one of (script, command) is required")

    if args:
        cmd += args

    try:
        return subprocess \
            .run(
            cmd,
            timeout=timeout,  # seconds
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) \
            .stdout \
            .decode('utf8') \
            .strip()
    except (subprocess.CalledProcessError, \
            subprocess.TimeoutExpired) as exc:
        raise RuntimeError(exc.stderr.decode('utf8') if exc.stderr else '')
