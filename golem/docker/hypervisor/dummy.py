from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Dict, Tuple, List

from golem.core.common import is_osx
from golem.docker.client import local_client
from golem.docker.config import GetConfigFunction, DOCKER_VM_NAME
from golem.docker.hypervisor import Hypervisor
from golem.docker.hypervisor.hyperv import HyperVHypervisor


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
        else:
            ip_address = net_config['Networks']['bridge']['IPAddress']

        port = int(net_config['Ports'][f'{port}/tcp'][0]['HostPort'])
        return ip_address, port


class DummyHyperVHypervisor(HyperVHypervisor):
    """ Hypervisor class that doesn't manage the VM state but does use
        HyperVHypervisor logic for directory sharing and port mapping. """

    __instance = None

    @classmethod
    def is_available(cls) -> bool:
        return True

    @classmethod
    def instance(
            cls,
            get_config_fn: GetConfigFunction,
            docker_vm: str = DOCKER_VM_NAME
    ) -> 'Hypervisor':
        # Do **NOT** use cls._instance because it is shared with superclass!
        if not cls.__instance:
            cls.__instance = cls._new_instance(get_config_fn, docker_vm)
        return cls.__instance

    def remove(self, name: Optional[str] = None) -> bool:
        return True

    def vm_running(self, name: Optional[str] = None) -> bool:
        return True

    def start_vm(self, name: Optional[str] = None) -> None:
        pass

    def stop_vm(self, name: Optional[str] = None) -> bool:
        return True

    def restore_vm(self, vm_name: Optional[str] = None) -> None:
        pass

    def save_vm(self, vm_name: Optional[str] = None) -> None:
        pass

    def create(self, vm_name: Optional[str] = None, **params) -> bool:
        return True

    def constrain(self, name: Optional[str] = None, **params) -> None:
        pass

    def constraints(self, name: Optional[str] = None) -> Dict:
        return {}

    def update_work_dirs(self, work_dirs: List[Path]) -> None:
        Hypervisor.update_work_dirs(self, work_dirs)

    @contextmanager
    def reconfig_ctx(self, name: Optional[str] = None):
        yield name or self._vm_name

    @contextmanager
    def restart_ctx(self, name: Optional[str] = None):
        yield name or self._vm_name

    @contextmanager
    def recover_ctx(self, name: Optional[str] = None):
        yield name or self._vm_name
