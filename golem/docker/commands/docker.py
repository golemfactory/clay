import logging
import subprocess
import time
from typing import List, Optional, Dict, Union, Callable, Tuple

from golem.core.common import SUBPROCESS_STARTUP_INFO, to_unicode


logger = logging.getLogger(__name__)


CallableCommand = Callable[
    [Optional[str], Union[Tuple, List[str], None], Optional[bool]],  # args
    Optional[str]  # return value
]

CommandDict = Dict[str, Union[List[str], CallableCommand]]


class DockerCommandHandler:

    TIMEOUT = 180

    commands: CommandDict = dict(
        build=['docker', 'build'],
        tag=['docker', 'tag'],
        pull=['docker', 'pull'],
        version=['docker', '-v'],
        help=['docker', '--help'],
        images=['docker', 'images', '-q'],
        info=['docker', 'info'],
    )

    @classmethod
    def run(cls,
            command_name: str,
            vm_name: Optional[str] = None,
            args: Optional[Union[Tuple, List[str]]] = None,
            shell: bool = False) -> Optional[str]:

        command = cls.commands.get(command_name)
        if not command:
            logger.error('Unknown command: %s', command_name)
        elif isinstance(command, list):
            return cls._command(command[:], vm_name, args, shell)
        elif callable(command):
            return command(vm_name, args, shell)
        return None

    @classmethod
    def wait_until_started(cls) -> None:
        started = time.time()
        done = None

        while not done:
            try:
                subprocess.check_output(['docker', 'info'],
                                        stderr=subprocess.DEVNULL)
                done = True
            except subprocess.CalledProcessError:
                time.sleep(1)
            except FileNotFoundError:
                logger.error('Docker: no such command: "docker"')
                return

            if time.time() - started >= cls.TIMEOUT:
                logger.error('Docker: VM start timeout')
                return

    @classmethod
    def _command(cls,
                 command: List[str],
                 vm_name: Optional[str] = None,
                 args: Optional[Union[Tuple, List[str]]] = None,
                 shell: bool = False) -> str:

        if args:
            command += list(args)
        if vm_name:
            command += [vm_name]

        logger.debug('Docker command: %s', command)

        try:
            output = subprocess.check_output(
                command,
                startupinfo=SUBPROCESS_STARTUP_INFO,
                shell=shell,
                stdin=subprocess.DEVNULL,
                stderr=subprocess.STDOUT
            )
        except FileNotFoundError as exc:
            raise subprocess.CalledProcessError(127, str(exc))

        logger.debug('Docker command output: %s', output)
        return to_unicode(output)
