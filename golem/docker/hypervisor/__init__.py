import logging
import subprocess
from abc import ABCMeta
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Optional, Iterable

from golem.docker.commands.docker import DockerCommandHandler
from golem.docker.config import DOCKER_VM_NAME, GetConfigFunction, \
    DOCKER_VM_STATUS_RUNNING
from golem.docker.task_thread import DockerBind
from golem.report import Component, report_calls

logger = logging.getLogger(__name__)


class Hypervisor(metaclass=ABCMeta):

    POWER_UP_DOWN_TIMEOUT = 30 * 1000  # milliseconds
    SAVE_STATE_TIMEOUT = 120 * 1000  # milliseconds
    COMMAND_HANDLER = DockerCommandHandler

    _instance = None

    def __init__(self,
                 get_config: GetConfigFunction,
                 vm_name: str = DOCKER_VM_NAME) -> None:

        self._get_config = get_config
        self._vm_name = vm_name
        self._work_dir: Optional[Path] = None

    @classmethod
    def is_available(cls) -> bool:
        return True

    def setup(self) -> None:
        if not self.vm_running():
            self.restore_vm()

    def quit(self) -> None:
        if self.vm_running():
            self.save_vm()

    @classmethod
    @report_calls(Component.hypervisor, 'instance.check')
    def instance(cls, get_config_fn: GetConfigFunction,
                 docker_vm: str = DOCKER_VM_NAME) -> 'Hypervisor':
        if not cls._instance:
            cls._instance = cls._new_instance(get_config_fn, docker_vm)
        return cls._instance

    @classmethod
    def _new_instance(
            cls,
            get_config_fn: GetConfigFunction,
            vm_name: str = DOCKER_VM_NAME) -> 'Hypervisor':
        return cls(get_config_fn, vm_name=vm_name)

    def command(self, *args, **kwargs) -> Optional[str]:
        return self.COMMAND_HANDLER.run(*args, **kwargs)

    def remove(self, name: Optional[str] = None) -> bool:
        name = name or self._vm_name
        logger.info("Hypervisor: removing VM '%s'", name)
        try:
            self.command('rm', name)
            return True
        except subprocess.CalledProcessError as e:
            logger.warning("Hypervisor: error removing VM '%s': %s", name, e)
        return False

    @report_calls(Component.docker, 'instance.check')
    def vm_running(self, name: Optional[str] = None) -> bool:
        name = name or self._vm_name
        if not name:
            raise EnvironmentError("Invalid Docker VM name")

        try:
            status = self.command('status', name) or ''
            status_lines = status.split("\n")
            for line in status_lines:
                if line == DOCKER_VM_STATUS_RUNNING:
                    return True
            return False
        except subprocess.CalledProcessError as e:
            logger.error("DockerMachine: failed to check status: %s", e)
        return False

    @report_calls(Component.docker, 'instance.start')
    def start_vm(self, name: Optional[str] = None) -> None:
        name = name or self._vm_name
        logger.info("Docker: starting VM %s", name)

        try:
            self.command('start', name)
        except subprocess.CalledProcessError as e:
            logger.error("Docker: failed to start the VM: %r", e)
            raise

    @report_calls(Component.docker, 'instance.stop')
    def stop_vm(self, name: Optional[str] = None) -> bool:
        name = name or self._vm_name
        logger.info("Docker: stopping %s", name)

        try:
            self.command('stop', name)
            return True
        except subprocess.CalledProcessError as e:
            logger.warning("Docker: failed to stop the VM: %r", e)
        return False

    def save_vm(self, vm_name: Optional[str] = None) -> None:
        logger.info("Docker: saving machine state not implemented")
        self.stop_vm(vm_name)

    def restore_vm(self, vm_name: Optional[str] = None) -> None:
        logger.info("Docker: restoring machine state not implemented")
        self.start_vm(vm_name)

    def create(self, vm_name: Optional[str] = None, **params) -> bool:
        raise NotImplementedError

    def _failed_to_create(self, vm_name: Optional[str] = None):
        raise NotImplementedError

    def constrain(self, name: Optional[str] = None, **params) -> None:
        raise NotImplementedError

    def constraints(self, name: Optional[str] = None) -> Dict:
        raise NotImplementedError

    @contextmanager
    def restart_ctx(self, name: Optional[str] = None):
        raise NotImplementedError

    @contextmanager
    def recover_ctx(self, name: Optional[str] = None):
        raise NotImplementedError

    def update_work_dir(self, work_dir: Path) -> None:
        self._work_dir = work_dir

    @staticmethod
    def uses_volumes() -> bool:
        return False

    def create_volumes(self, binds: Iterable[DockerBind]) -> dict:
        raise NotImplementedError
