import logging
import subprocess
import sys
import time
from typing import Optional

from golem.core.common import unix_pid
from golem.docker.commands.docker import CommandDict, DockerCommandHandler
from golem.docker.config import DOCKER_VM_STATUS_RUNNING

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
        pid = cls.pid()
        if not pid:
            return

        try:
            subprocess.check_call(['kill', str(pid)])
        except subprocess.CalledProcessError:
            logger.error('Docker for Mac: unable to stop the app')
            return

        cls.wait_until_stopped()

    @classmethod
    def pid(cls) -> Optional[int]:
        return unix_pid(cls.PROCESSES['app'])

    @classmethod
    def status(cls) -> str:
        return DOCKER_VM_STATUS_RUNNING if cls.pid() else ''

    @classmethod
    def wait_until_stopped(cls) -> None:
        started = time.time()

        while any(map(unix_pid, cls.PROCESSES.values())):
            if time.time() - started >= cls.TIMEOUT:
                logger.error('Docker for Mac: VM start timeout')
                return
            time.sleep(0.5)

    # pylint: disable=undefined-variable
    commands: CommandDict = dict(
        start=lambda *_: DockerForMacCommandHandler.start(),
        stop=lambda *_: DockerForMacCommandHandler.stop(),
        status=lambda *_: DockerForMacCommandHandler.status(),
    )

    commands.update(DockerCommandHandler.commands)
