import logging
from contextlib import contextmanager
from typing import Dict, Optional

from golem.core.common import is_windows
from golem.docker.config import CONSTRAINT_KEYS, DOCKER_VM_NAME, \
    GetConfigFunction
from golem.docker.hypervisor import Hypervisor
from golem.docker.hypervisor.docker_machine import DockerMachineHypervisor
from golem.report import Component, report_calls

logger = logging.getLogger(__name__)


class VirtualBoxHypervisor(DockerMachineHypervisor):

    DRIVER_NAME = 'virtualbox'

    power_down_states = [
        'Saved', 'Aborted'
    ]

    running_states = [
        'Running', 'FirstOnline', 'LastOnline'
    ]

    # noqa # pylint: disable=too-many-arguments
    def __init__(self,
                 get_config_fn: GetConfigFunction,
                 virtualbox, ISession, LockType,
                 vm_name: str = DOCKER_VM_NAME) -> None:
        super(VirtualBoxHypervisor, self).__init__(get_config_fn, vm_name)

        if is_windows():
            import pythoncom  # noqa # pylint: disable=import-error
            pythoncom.CoInitialize()

        self.virtualbox = virtualbox
        self.ISession = ISession
        self.LockType = LockType

    @contextmanager
    @report_calls(Component.hypervisor, 'vm.restart')
    def restart_ctx(self, name: Optional[str] = None):
        name = name or self._vm_name
        immutable_vm = self._machine_from_arg(name)
        if not immutable_vm:
            yield None
            return

        running = self.vm_running()
        if running:
            self.stop_vm()

        session = immutable_vm.create_session(self.LockType.write)
        vm = session.machine

        if str(vm.state) in self.power_down_states:
            self.power_down(session)

        try:
            yield vm
        except Exception as e:
            logger.error("VirtualBox: VM restart error: %r", e)

        vm.save_settings()

        try:
            session.unlock_machine()
        except Exception as e:
            logger.warning("VirtualBox: error unlocking VM '%s': %r", name, e)

        if running:
            self.start_vm()
        self._set_env()

    @contextmanager
    @report_calls(Component.hypervisor, 'vm.recover')
    def recover_ctx(self, name: Optional[str] = None):
        name = name or self._vm_name
        immutable_vm = self._machine_from_arg(name)
        if not immutable_vm:
            yield None
            return

        session = immutable_vm.create_session(self.LockType.shared)
        vm = session.machine

        if str(vm.state) in self.running_states:
            self._save_state(session)

        try:
            yield vm
        except Exception as e:
            logger.error("VirtualBox: recovery error: {}"
                         .format(e))

        try:
            session.unlock_machine()
        except Exception as e:
            logger.warn("VirtualBox: error unlocking VM '{}': {}"
                        .format(name, e))

        self.start_vm()
        self._set_env()

    def constraints(self, name: Optional[str] = None) -> Dict:
        result = {}
        try:
            vm = self._machine_from_arg(name)
            for constraint_key in CONSTRAINT_KEYS.values():
                result[constraint_key] = getattr(vm, constraint_key)
        except Exception as e:
            logger.error("VirtualBox: error reading VM's constraints: {}"
                         .format(e))
        return result

    def constrain(self, name: Optional[str] = None, **params) -> None:
        vm = self._machine_from_arg(name)
        if not vm:
            return

        for key, value in params.items():
            try:
                setattr(vm, key, value)
            except Exception as e:
                logger.error('VirtualBox: error setting {} to {}: {}'
                             .format(key, value, e))

        logger.info("VirtualBox: VM '{}' reconfiguration finished"
                    .format(vm.name))

    def power_up(self, vm_or_session, lock_type=None):
        """
        Power up a machine identified by the mixed param
        :param vm_or_session: Machine id, name, Machine object or Session object
        :param lock_type: Session lock type
        :return: Session object
        """
        try:
            session = self._session_from_arg(vm_or_session,
                                             lock_type=lock_type)
            logger.debug("VirtualBox: starting VM '{}'"
                         .format(session.machine.name))

            progress = session.console.power_up()
            progress.wait_for_completion(timeout=self.POWER_UP_DOWN_TIMEOUT)
            return session

        except Exception as e:
            logger.error("VirtualBox: error starting a VM: '{}'"
                         .format(e))
        return None

    def power_down(self, vm_or_session, lock_type=None):
        """
        Power down a machine identified by the mixed param
        :param vm_or_session: Machine id, name, Machine object or Session object
        :param lock_type: Session lock type
        :return: Session object
        """
        try:
            session = self._session_from_arg(vm_or_session,
                                             lock_type=lock_type)
            logger.debug("VirtualBox: stopping VM '{}'"
                         .format(session.machine.name))

            progress = session.console.power_down()
            progress.wait_for_completion(timeout=self.POWER_UP_DOWN_TIMEOUT)
            return session

        except Exception as e:
            logger.error("VirtualBox: error stopping a VM: '{}'"
                         .format(e))
        return None

    def _save_state(self, vm_or_session, lock_type=None):
        try:
            session = self._session_from_arg(vm_or_session,
                                             lock_type=lock_type)
            logger.debug("VirtualBox: saving state of VM '{}'"
                         .format(session.machine.name))

            progress = session.machine.save_state()
            progress.wait_for_completion(timeout=self.SAVE_STATE_TIMEOUT)
            return session

        except Exception as e:
            logger.error("VirtualBox: error saving VM's state: '{}'"
                         .format(e))
        return None

    def _session_from_arg(self, session_obj, lock_type=None):
        if not isinstance(session_obj, self.ISession):
            vm = self._machine_from_arg(session_obj)
            lock_type = lock_type or self.LockType.null
            if vm:
                return vm.create_session(lock_type)
            return None
        return session_obj

    def _machine_from_arg(self, machine_obj):
        if isinstance(machine_obj, str):
            try:
                return self.virtualbox.find_machine(machine_obj)
            except Exception as e:
                logger.error('VirtualBox: machine {} not found: {}'
                             .format(machine_obj, e))
                return None
        return machine_obj

    @classmethod
    def _new_instance(cls,
                      get_config_fn: GetConfigFunction,
                      docker_vm: str = DOCKER_VM_NAME) -> Hypervisor:
        try:
            from virtualbox import VirtualBox
            from virtualbox.library import ISession, LockType
        except ImportError as err:
            logger.error('Error importing VirtualBox libraries: %r', err)
            raise

        return VirtualBoxHypervisor(get_config_fn, docker_vm,
                                    VirtualBox(), ISession, LockType)
