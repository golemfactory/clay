from typing import Optional, Dict, Tuple

from golem.docker.client import local_client
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

    def requires_ports_publishing(self) -> bool:
        return False

    def get_port_mapping(self, container_id: str, port: int) -> Tuple[str, int]:
        api_client = local_client()
        c_config = api_client.inspect_container(container_id)
        ip_address = \
            c_config['NetworkSettings']['Networks']['bridge']['IPAddress']
        return ip_address, port
