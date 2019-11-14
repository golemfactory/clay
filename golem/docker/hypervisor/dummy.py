from typing import Optional, Dict, Tuple

from golem.core.common import is_osx, is_windows
from golem.docker.client import local_client
from golem.docker.commands.docker_machine import DockerMachineCommandHandler
from golem.docker.config import DOCKER_VM_NAME
from golem.docker.hypervisor import Hypervisor


class DummyHypervisor(Hypervisor):
    """
    A simple class which is meant to be used in environments where Docker can
    be used without a hypervisor. It simplifies code by avoiding conditional
    statements which check is hypervisor is needed.
    """

    @classmethod
    def is_available(cls) -> bool:
        return True

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def remove(self, name: Optional[str] = None) -> bool:
        return True

    def vm_running(self, name: Optional[str] = None) -> bool:
        return True

    def start_vm(self, name: Optional[str] = None) -> None:
        pass

    def stop_vm(self, name: Optional[str] = None) -> bool:
        return True

    def create(self, vm_name: Optional[str] = None, **params) -> bool:
        return True

    def constrain(self, name: Optional[str] = None, **params) -> None:
        pass

    def constraints(self, name: Optional[str] = None) -> Dict:
        return {}

    def get_port_mapping(self, container_id: str, port: int) -> Tuple[str, int]:
        api_client = local_client()
        config = api_client.inspect_container(container_id)
        net_config = config['NetworkSettings']

        # TODO: Remove if-s when NonHypervisedDockerCPUEnvironment is removed
        if is_osx():
            ip_address = '127.0.0.1'
        elif is_windows():
            vm_ip = DockerMachineCommandHandler.run('ip', DOCKER_VM_NAME)
            if vm_ip is None:
                raise RuntimeError('Cannot retrieve Docker VM IP address')
            ip_address = vm_ip
        else:
            ip_address = net_config['Networks']['bridge']['IPAddress']

        port = int(net_config['Ports'][f'{port}/tcp'][0]['HostPort'])
        return ip_address, port
