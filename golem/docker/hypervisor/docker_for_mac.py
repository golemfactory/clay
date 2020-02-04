import json
import logging
import os
from contextlib import contextmanager
from typing import Dict, Optional, Tuple

from golem.docker.client import local_client
from golem.docker.commands.docker_for_mac import DockerForMacCommandHandler
from golem.docker.config import CONSTRAINT_KEYS
from golem.docker.hypervisor import Hypervisor
from golem.report import Component, report_calls

logger = logging.getLogger(__name__)


class DockerForMac(Hypervisor):
    """ Implements Docker for Mac integration as a hypervisor. """

    COMMAND_HANDLER = DockerForMacCommandHandler

    CONFIG_FILE = os.path.expanduser(
        "~/Library/Group Containers/group.com.docker/settings.json"
    )
    CONFIG_KEYS = dict(
        cpu='cpus',
        mem='memoryMiB',
    )
    DAEMON_CONFIG_FILE = os.path.expanduser(
        "~/.docker/daemon.json"
    )

    DNS_SERVERS = [
        '1.1.1.1',  # Cloudflare
        '208.67.222.222',  # OpenDNS
        '8.8.8.8',  # Google
    ]

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
            self._update_config(update)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Docker for Mac: unable to update config: %r", e)

    def constraints(self, name: Optional[str] = None) -> Dict:
        config = self._read_config()
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

    def get_port_mapping(self, container_id: str, port: int) -> Tuple[str, int]:
        api_client = local_client()
        c_config = api_client.inspect_container(container_id)
        port = int(
            c_config['NetworkSettings']['Ports'][f'{port}/tcp'][0]['HostPort'])
        return '127.0.0.1', port

    def _configure_daemon(self) -> None:
        update = {'dns': self.DNS_SERVERS}
        self._update_daemon_config(update)

    def _read_config(self) -> Dict:
        if not os.path.exists(self.CONFIG_FILE):
            self.start_vm()
        if not os.path.exists(self.CONFIG_FILE):
            raise RuntimeError('Docker for Mac: unable to read VM config')

        with open(self.CONFIG_FILE) as config_file:
            return json.load(config_file)

    def _update_config(self, update: Dict) -> None:
        config = self._read_config()
        config.update(update)

        with open(self.CONFIG_FILE, 'w') as config_file:
            json.dump(config, config_file)

    def _read_daemon_config(self) -> Dict:
        if not os.path.exists(self.DAEMON_CONFIG_FILE):
            return dict()

        with open(self.DAEMON_CONFIG_FILE) as config_file:
            return json.load(config_file)

    def _update_daemon_config(self, update: Dict) -> None:
        config = self._read_daemon_config()
        config.update(update)

        docker_dir = os.path.dirname(self.DAEMON_CONFIG_FILE)
        os.makedirs(docker_dir, mode=0o750, exist_ok=True)

        with open(self.DAEMON_CONFIG_FILE, 'w') as config_file:
            json.dump(config, config_file)

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
