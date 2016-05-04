import logging
import time
from contextlib import contextmanager
from threading import Thread

import subprocess

from virtualbox import VirtualBox
from virtualbox.library import IMachine, ISession

from golem.docker.config_manager import DockerConfigManager

logger = logging.getLogger(__name__)


class DockerVirtualBoxManager(DockerConfigManager):

    docker_vm_list_commands = [
        ['docker_machine', 'ls', '-q']
    ]

    resumable_states = [
        'Saved'
    ]
    running_states = [
        'Running',
        'DeletingSnapshot'
    ]
    stopped_states = [
        'PoweredOff',
        'Aborted',
        'Paused',
        'Stuck'
    ]
    transitioning_states = [
        'Starting',
        'Stopping',
        'Saving',
        'Restoring',
        'LiveSnapshotting',
        'RestoringSnapshot',
        'SettingUp'
    ]
    invalid_states = [
        'Null',
        'Teleported',
        'TeleportingPausedVM',
        'TeleportingIn',
        'FaultTolerantSyncing',
        'DeletingSnapshotOnline',
        'DeletingSnapshotPaused',
        'OnlineSnapshotting',
    ]

    constraint_keys = [
        'memory_size', 'cpu_count', 'cpu_execution_cap'
    ]

    def __init__(self,
                 default_memory_size=1024,
                 default_cpu_execution_cap=100,
                 default_cpu_count=1,
                 min_memory_size=1024,
                 min_cpu_execution_cap=1,
                 min_cpu_count=1):

        self.api = VirtualBox()
        self.__vm_api_dict = IMachine.__dict__

        self.virtual_box_available = False
        self.docker_images = []
        self.config_thread = None
        self.check_environment()

        self.min_constraints = dict(
            memory_size=min_memory_size,
            cpu_execution_cap=min_cpu_execution_cap,
            cpu_count=min_cpu_count
        )

        self.defaults = dict(
            memory_size=default_memory_size,
            cpu_count=default_cpu_count,
            cpu_execution_cap=default_cpu_execution_cap
        )

        self.virtualbox_config = self.defaults

    def check_environment(self):
        try:
            # check virtualbox availability
            _ = self.api.version
            # check docker image availability
            for command in self.docker_vm_list_commands:
                try:
                    output = subprocess.check_output(command)
                    self.docker_images = [i.strip() for i in output.split("\n")]
                    self.virtual_box_available = True
                    return
                except:
                    pass
        except Exception as e:
            logger.warn("VirtualBox: not available - {}"
                        .format(e.message))
        self.virtual_box_available = False

        logger.debug("VirtualBox: available = {}, images = {}"
                     .format(self.virtual_box_available, self.docker_images))

    def find_machine(self, name_or_id):
        return self.api.find_machine(name_or_id)

    def start_machine(self, mixed):
        """
        Start a machine identified by the mixed param
        :param mixed: Machine id, name, Machine object or Session object
        :return: Session object
        """
        return self.__start_vm(mixed)

    def stop_machine(self, mixed):
        """
        Stop a machine identified by the mixed param
        :param mixed: Machine id, name, Machine object or Session object
        :return: Session object
        """
        return self.__stop_vm(mixed)

    def constraints(self, name_or_id_or_machine):
        try:
            vm = self.__machine_from_arg(name_or_id_or_machine)
            if not vm:
                return

            result = {}
            for constraint_key in self.constraint_keys:
                result[constraint_key] = getattr(vm, constraint_key)
            return result
        except Exception as e:
            logger.error("Virtualbox: error reading VM's constraints: {}"
                         .format(e.message))

    def constrain(self, name_or_id_or_machine, **kwargs):
        logger.debug("VirtualBox: reconfiguring {} with {}"
                     .format(name_or_id_or_machine, kwargs))

        if not kwargs:
            kwargs = self.virtualbox_config

        try:
            self.__constrain(name_or_id_or_machine, **kwargs)
        except Exception as e:
            logger.error("VirtualBox: error setting {} VM's constraints: {}"
                         .format(name_or_id_or_machine, e.message))

    def constrain_in_background(self, success, failure, **kwargs):
        if self.config_thread:
            self.config_thread.join()

        self.__constrain_thread(self.docker_images,
                                success=success,
                                failure=failure,
                                kwargs=kwargs).run()

    def defaults(self, name_or_id_or_machine):
        try:
            self.__constrain(name_or_id_or_machine, **self.defaults)
        except Exception as e:
            logger.error("VirtualBox: error setting VM's defaults: {}"
                         .format(e.message))

    def build_config(self, config_desc):
        super(DockerVirtualBoxManager, self).build_config(config_desc)
        self.virtualbox_config = dict(
            memory_size=config_desc.max_memory_size,
            cpu_count=config_desc.num_cores
        )

    @contextmanager
    def __restart_ctx(self, name_or_id_or_machine, restart=True):
        vm = self.__machine_from_arg(name_or_id_or_machine)
        if not vm:
            return

        state = str(vm.state())
        session = None
        stopped = False

        if restart:
            while session is None:
                session, stopped = self.__stop_by_state(vm, state)
                time.sleep(0.5)

        yield

        if restart and stopped:
            self.__start_vm(session)

    def __start_vm(self, vm_or_session):
        logger.debug('Virtualbox: starting {}'.format())
        try:
            session = self.__session_from_arg(vm_or_session)
            session.console.power_up()
            return session
        except Exception as e:
            logger.error('VirtualBox: error starting a VM: {}'
                         .format(e.message))
        return None

    def __stop_vm(self, vm_or_session):
        logger.debug('VirtualBox: stopping {}'.format(vm_or_session))
        try:
            session = self.__session_from_arg(vm_or_session)
            session.console.power_down()
            return session
        except Exception as e:
            logger.error('VirtualBox: error stopping a VM: {}'
                         .format(e.message))
        return None

    def __stop_by_state(self, vm, state):
        if state in self.stopped_states:
            return vm.create_session(), True
        elif state in self.transitioning_states:
            return None, False
        elif state in self.invalid_states:
            raise EnvironmentError("VM is in invalid state: {}".format(state))
        return vm.stop_machine(vm), True

    def __constrain(self, machine_obj, **kwargs):
        vm = self.__machine_from_arg(machine_obj)
        if not vm:
            return

        restart = kwargs.pop('restart', False)
        force = kwargs.pop('force', False)

        constraints = self.constraints(vm)
        constraint_diff = self.__constraint_diff(constraints, kwargs)

        if not constraint_diff:
            logger.debug("VirtualBox: {} VM's configuration unchanged"
                         .format(vm.name))
            return

        with self.__restart_ctx(vm, restart=restart):
            self.__apply_constraints(vm, constraint_diff, force=force)

    def __constraint_diff(self, old_values, new_values):
        result = {}

        for constraint_key in self.constraint_keys:
            old_value = old_values.get(constraint_key)
            new_value = new_values.get(constraint_key)

            if new_value != old_value and new_value is not None:
                result[constraint_key] = new_value

        return result

    def __constrain_thread(self, images, success, failure, **kwargs):

        def method():
            exc = None
            for image_name in images:
                try:
                    self.constrain(image_name, **kwargs)
                except Exception as e:
                    exc = e
            if exc:
                failure(exc, images)
            else:
                success(images)
            self.config_thread = None

        return Thread(target=method)

    def __apply_constraints(self, vm, params, force=False):
        for name, value in params:
            if name in self.__vm_api_dict:
                min_val = self.min_constraints.get(name)

                if force or min_val is None:
                    cur_val = value
                else:
                    cur_val = max(min_val, value)

                try:
                    setattr(vm, name, cur_val)
                except Exception as e:
                    logger.error('VirtualBox: error constraining VM {}: {}'
                                 .format(name, e.message))

    def __session_from_arg(self, session_obj):
        if not isinstance(session_obj, ISession):
            vm = self.__machine_from_arg(session_obj)
            return vm.create_session() if vm else None
        return session_obj

    def __machine_from_arg(self, machine_obj):
        if isinstance(machine_obj, basestring):
            try:
                return self.find_machine(machine_obj)
            except Exception as e:
                logger.error('VirtualBox: machine {} not found: {}'
                             .format(machine_obj, e.message))
                return None
        return machine_obj
