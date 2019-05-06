import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Optional

from golem.docker.commands.docker_for_mac import DockerForMacCommandHandler
from golem.docker.config import CONSTRAINT_KEYS, GetConfigFunction, \
    DOCKER_VM_NAME, DNS_SERVERS
from golem.core.json_config import JsonFileConfig
from golem.docker.hypervisor import Hypervisor
from golem.report import Component, report_calls

logger = logging.getLogger(__name__)


class DockerForMacConfig(JsonFileConfig):

    def __init__(self) -> None:
        super().__init__(
            Path.home() / "Library" / "Group Containers" /
            "group.com.docker" / "settings.json"
        )


class DockerForMacDaemonConfig(JsonFileConfig):

    def __init__(self) -> None:
        super().__init__(
            Path.home() / ".docker" / "daemon.json"
        )


class DockerForMac(Hypervisor):
    """ Implements Docker for Mac integration as a hypervisor. """

    COMMAND_HANDLER = DockerForMacCommandHandler

    CONFIG_KEYS = dict(
        cpu='cpus',
        mem='memoryMiB',
    )

    def __init__(self, get_config: GetConfigFunction,
                 vm_name: str = DOCKER_VM_NAME) -> None:

        super().__init__(get_config, vm_name)

        self._config = DockerForMacConfig()
        self._daemon_config = DockerForMacDaemonConfig()

    def setup(self) -> None:
        if self.vm_running():
            # wait until Docker is ready
            self.COMMAND_HANDLER.wait_until_started()
        else:
            self._configure_daemon()
            self.start_vm()

    @classmethod
    def is_available(cls) -> bool:
        return os.path.exists(cls.COMMAND_HANDLER.APP)

    def create(self, vm_name: Optional[str] = None, **params) -> bool:
        # We do not control VM creation
        return False

    def remove(self, name: Optional[str] = None) -> bool:
        # We do not control VM removal
        return False

    def constrain(self, name: Optional[str] = None, **params) -> None:
        update = {
            config_key: params.get(CONSTRAINT_KEYS[key])
            for key, config_key in self.CONFIG_KEYS.items()
        }

        try:
            self._config.update(update)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Docker for Mac: unable to update config: %r", e)

    def constraints(self, name: Optional[str] = None) -> Dict:
        config = self._config.read()
        constraints = dict()

        try:
            constraints[CONSTRAINT_KEYS['cpu']] = int(config['cpus'])
        except (KeyError, ValueError, TypeError) as e:
            logger.error("Docker for Mac: error reading CPU count: %r", e)

        try:
            constraints[CONSTRAINT_KEYS['mem']] = int(config['memoryMiB'])
        except (KeyError, ValueError, TypeError) as e:
            logger.error("Docker for Mac: error reading memory size: %r", e)

        return constraints

    def _configure_daemon(self) -> None:
        update = {'dns': DNS_SERVERS}
        self._daemon_config.update(update)

    @contextmanager
    @report_calls(Component.hypervisor, 'vm.restart')
    def restart_ctx(self, name: Optional[str] = None):
        if self.vm_running():
            self.stop_vm()
        yield name
        self.start_vm()

    @contextmanager
    @report_calls(Component.hypervisor, 'vm.recover')
    def recover_ctx(self, name: Optional[str] = None):
        self.restart_ctx(name)
