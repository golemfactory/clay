import logging
import subprocess
import time
from typing import List, Optional

from golem.core.common import SUBPROCESS_STARTUP_INFO, DEVNULL, to_unicode


logger = logging.getLogger(__name__)


class DockerCommandHandler:

    commands = dict(
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
            args: Optional[List[str]] = None,
            shell: bool = False) -> str:

        command = cls.commands.get(command_name)
        if isinstance(command, list):
            return cls._command(command[:], vm_name, args, shell)
        elif callable(command):
            return command(vm_name, args, shell)
        return str()

    @classmethod
    def wait_until_started(cls):
        started = time.time()
        done = None

        while not done:
            try:
                subprocess.check_output(['docker', 'info'],
                                        stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError:
                time.sleep(1)
            else:
                done = True

            if time.time() - started >= cls.TIMEOUT:
                logger.error('Docker: VM start timeout')
                return

    @classmethod
    def _command(cls,
                 command: List[str],
                 vm_name: Optional[str] = None,
                 args: Optional[List[str]] = None,
                 shell: bool = False) -> str:

        if args:
            command += args
        if vm_name:
            command += [vm_name]

        logger.debug('Docker command: %s', command)

        try:
            output = subprocess.check_output(
                command,
                startupinfo=SUBPROCESS_STARTUP_INFO,
                shell=shell,
                stdin=DEVNULL,
                stderr=subprocess.STDOUT
            )
        except subprocess.CalledProcessError as exc:
            logger.error("Docker: error executing command: %r", command)
            logger.debug("Docker error output: %r", exc.output)
            output = str()

        logger.debug('Docker command output: %s', output)
        return to_unicode(output)
