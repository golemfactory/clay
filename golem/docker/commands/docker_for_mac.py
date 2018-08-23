import logging
import subprocess
import sys
import time
from typing import List, Optional

from golem.docker.commands.docker import CommandDict, DockerCommandHandler

logger = logging.getLogger(__name__)


class DockerForMacCommandHandler(DockerCommandHandler):

    APP = '/Applications/Docker.app'
    PROCESSES = dict(
        app=f'{APP}/Contents/MacOS/Docker',
        driver='com.docker.driver',
        hyperkit='com.docker.hyperkit',
        vpnkit='com.docker.vpnkit',
    )

    @classmethod
    def start(cls, *_args, **_kwargs) -> None:
        try:
            subprocess.check_call(['open', '-g', '-a', cls.PROCESSES['app']])
            cls.wait_until_started()
        except (FileNotFoundError, subprocess.CalledProcessError):
            logger.error('Docker for Mac: unable to start the app')
            sys.exit(1)

    @classmethod
    def stop(cls) -> None:
        pid = cls._pid()
        if not pid:
            return

        try:
            subprocess.check_call(['kill', str(pid)])
        except subprocess.CalledProcessError:
            return

        cls.wait_until_stopped()

    @classmethod
    def status(cls) -> str:
        return 'Running' if cls._pid() else ''

    @classmethod
    def wait_until_stopped(cls):
        started = time.time()

        while any(map(cls._pid, cls.PROCESSES)):
            if time.time() - started >= cls.TIMEOUT:
                logger.error('Docker for Mac: VM start timeout')
                return
            time.sleep(0.5)

    @classmethod
    def _pid(cls, key: str = 'app') -> Optional[int]:

        process_name = cls.PROCESSES[key]
        process_name = f'[{process_name[0]}]{process_name[1:]}'

        try:
            line = cls._pipe(['ps', 'ux'], ['grep', '-i', process_name])
        except (FileNotFoundError, subprocess.CalledProcessError):
            return None

        try:
            return int(line.split()[1])
        except (IndexError, TypeError, ValueError):
            return None

    @staticmethod
    def _pipe(cmd: List[str], pipe: List[str]):
        proc_cmd = subprocess.Popen(cmd,
                                    stdout=subprocess.PIPE)
        proc_pipe = subprocess.Popen(pipe,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     stdin=proc_cmd.stdout)
        proc_cmd.stdout.close()
        stdout, _ = proc_pipe.communicate()
        return stdout.strip().decode('utf-8')

    # pylint: disable=undefined-variable
    commands: CommandDict = dict(
        start=lambda *_: DockerForMacCommandHandler.start(),
        stop=lambda *_: DockerForMacCommandHandler.stop(),
        status=lambda *_: DockerForMacCommandHandler.status(),
    )

    commands.update(DockerCommandHandler.commands)
