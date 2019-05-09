from typing import Optional, Dict

from golem.docker.hypervisor import Hypervisor


class DummyHypervisor(Hypervisor):
    """
    A simple class which implements Hypervisor interface and effectively does
    nothing. It is meant to be used in environments where Docker can be used
    without a hypervisor. It simplifies code by avoiding conditional statements
    which check is hypervisor is needed.
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
        pass

    def create(self, vm_name: Optional[str] = None, **params) -> bool:
        pass

    def constrain(self, name: Optional[str] = None, **params) -> None:
        pass

    def constraints(self, name: Optional[str] = None) -> Dict:
        pass
