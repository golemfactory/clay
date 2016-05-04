import logging
import subprocess
from contextlib import contextmanager

import time
from threading import Thread

from virtualbox import VirtualBox
from virtualbox.library import ISession, LockType

from golem.docker.config_manager import DockerConfigManager

logger = logging.getLogger(__name__)


class DockerMachineManager(DockerConfigManager):

    POWER_UP_DOWN_TIMEOUT = 60 * 1000

    docker_machine_commands = dict(
        list=['docker-machine', 'ls', '-q'],
        stop=['docker-machine', 'stop'],
        start=['docker-machine', 'start'],
        status=['docker-machine', 'status'],
        env=['docker-machine', 'env']
    )

    power_down_states = [
        'Saved', 'Aborted'
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

        self.docker_machine_available = False
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
        self._threads = []

    def shutdown(self):
        for t in self._threads:
            t.join()

    def check_environment(self):
        try:
            # check machine availability
            if not self.api.version:
                raise EnvironmentError("unknown version")

            # check docker image availability
            command = self.docker_machine_commands['list']
            output = subprocess.check_output(command, shell=True)

            self.docker_images = [i.strip() for i in output.split("\n") if i]
            self.docker_machine_available = True
            return

        except Exception as e:
            logger.warn("VirtualBox: not available - {}"
                        .format(e.message))
        self.docker_machine_available = False

        logger.debug("VirtualBox: available = {}, images = {}"
                     .format(self.docker_machine_available,
                             self.docker_images))

    def update_config(self, status_callback, done_callback, in_background=True):

        def wait_for_tasks():
            while status_callback():
                time.sleep(0.5)
            self.constrain_all()
            done_callback()
            if thread in self._threads:
                self._threads.remove(thread)

        thread = Thread(target=wait_for_tasks)

        if in_background:
            self._threads.append(thread)
            thread.start()
        else:
            thread.run()

    def find_vm(self, name_or_id):
        return self.api.find_machine(name_or_id)

    def start_vm(self, mixed):
        """
        Power up a machine identified by the mixed param
        :param mixed: Machine id, name, Machine object or Session object
        :return: Session object
        """
        return self.__power_up_vm(mixed)

    def stop_vm(self, mixed, lock_type=None):
        """
        Power down a machine identified by the mixed param
        :param mixed: Machine id, name, Machine object or Session object
        :param lock_type: Session lock type
        :return: Session object
        """
        return self.__power_down_vm(mixed, lock_type=lock_type)

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
        constraints = kwargs or self.virtualbox_config

        logger.debug("VirtualBox: reconfiguring '{}' with {}"
                     .format(name_or_id_or_machine, constraints))

        try:
            self.__constrain(name_or_id_or_machine, **constraints)
        except Exception as e:
            logger.error("VirtualBox: error setting '{}' VM's constraints: {}"
                         .format(name_or_id_or_machine, e.message))

    def constrain_all(self, images=None, **kwargs):
        exception = None
        for image_name in images or self.docker_images:
            try:
                self.constrain(image_name, **kwargs)
            except Exception as exc:
                exception = exc
        if exception:
            raise exception

    def constrain_in_background(self, success, failure, **kwargs):
        if self.config_thread:
            self.config_thread.join()

        self.constrain_all(self.docker_images,
                           success=success,
                           failure=failure,
                           **kwargs).run()

    def build_config(self, config_desc):
        super(DockerMachineManager, self).build_config(config_desc)

        cpu_count = self.min_constraints['cpu_count']
        memory_size = self.min_constraints['memory_size']

        with self._try():
            cpu_count = max(int(config_desc.num_cores), cpu_count)

        with self._try():
            memory_size += int(config_desc.max_memory_size) / 1000

        self.virtualbox_config = dict(
            memory_size=memory_size,
            cpu_count=cpu_count
        )

    @contextmanager
    def __restart_ctx(self, name_or_id_or_machine, restart=True):
        vm = self.__machine_from_arg(name_or_id_or_machine)
        if not vm:
            return

        running = self.__docker_machine_running()
        if restart and running:
            self.__stop_docker_machine()

        session = vm.create_session(LockType.write)
        mutable_vm = session.machine
        exception = None

        if str(vm.state) in self.power_down_states:
            self.stop_vm(session)

        try:
            yield mutable_vm
        except Exception as e:
            exception = e

        mutable_vm.save_settings()

        with self._try():
            session.unlock_machine()
            session.disconnect()

        if restart or not running:
            self.__start_docker_machine()
        if exception:
            logger.error("DockerMachine: restart context error: {}"
                         .format(exception.message))

    def __docker_machine_running(self):
        try:
            status = subprocess.check_output(self.docker_machine_commands['status'])
            status = status.strip().replace("\n", "")
            return status == 'Running'
        except Exception as e:
            logger.error("DockerMachine: failed to check docker-machine status: {}"
                         .format(e.message))
        return False

    def __start_docker_machine(self):
        logger.debug("DockerMachine: starting")
        try:
            subprocess.check_output(self.docker_machine_commands['start'])
            subprocess.check_output(self.docker_machine_commands['env'],
                                    shell=True)
        except Exception as e:
            logger.error("DockerMachine: failed to start the VM: {}"
                         .format(e.message))

    def __stop_docker_machine(self):
        logger.debug("DockerMachine: stopping")
        try:
            command = self.docker_machine_commands['stop']
            subprocess.check_call(command)
            return True
        except Exception as e:
            logger.warn("DockerMachine: failed to stop the VM: {}"
                        .format(e.message))
        return False

    def __power_up_vm(self, vm_or_session, lock_type=None):
        try:
            session = self.__session_from_arg(vm_or_session,
                                              lock_type=lock_type)
            logger.debug("VirtualBox: starting VM '{}'"
                         .format(session.machine.name))

            progress = session.console.power_up()
            progress.wait_for_completion(timeout=self.POWER_UP_DOWN_TIMEOUT)
            return session
        except Exception as e:
            logger.error("VirtualBox: error starting a VM: '{}'"
                         .format(e.message))
        return None

    def __power_down_vm(self, vm_or_session, lock_type=None):
        try:
            session = self.__session_from_arg(vm_or_session,
                                              lock_type=lock_type)
            logger.debug("VirtualBox: stopping VM '{}'"
                         .format(session.machine.name))

            progress = session.console.power_down()
            progress.wait_for_completion(timeout=self.POWER_UP_DOWN_TIMEOUT)
            return session

        except Exception as e:
            logger.error("VirtualBox: error stopping a VM: '{}'"
                         .format(e.message))
        return None

    def __constrain(self, machine_obj, **kwargs):
        vm = self.__machine_from_arg(machine_obj)
        if not vm:
            return

        constraints = self.constraints(vm)
        diff = self.__diff_constraints(constraints, kwargs)

        restart = kwargs.pop('restart', True)
        force = kwargs.pop('force', False)

        if diff:
            with self.__restart_ctx(vm, restart=restart) as mutable_vm:
                self.__apply_constraints(mutable_vm, diff, force=force)
        else:
            if not self.__docker_machine_running():
                self.__start_docker_machine()
            logger.debug("VirtualBox: '{}' VM's configuration unchanged"
                         .format(vm.name))

    def __diff_constraints(self, old_values, new_values):
        result = dict()

        for constraint_key in self.constraint_keys:
            old_value = old_values.get(constraint_key)
            new_value = new_values.get(constraint_key)

            if new_value != old_value and new_value is not None:
                result[constraint_key] = new_value

        return result

    def __apply_constraints(self, vm, params, force=False):
        if not params:
            return

        for name, value in params.iteritems():
            min_val = self.min_constraints.get(name)

            if force or min_val is None:
                cur_val = value
            else:
                cur_val = max(min_val, value)

            try:
                setattr(vm, name, cur_val)
            except:
                logger.error('VirtualBox: error setting {} to {}'
                             .format(name, value))

        logger.debug('VirtualBox: VM {} reconfigured successfully'
                     .format(vm.name))

    def __session_from_arg(self, session_obj, lock_type=None):
        if not isinstance(session_obj, ISession):
            vm = self.__machine_from_arg(session_obj)
            lock_type = lock_type or LockType.null
            if vm:
                return vm.create_session(lock_type)
            return None
        return session_obj

    def __machine_from_arg(self, machine_obj):
        if isinstance(machine_obj, basestring):
            try:
                return self.find_vm(machine_obj)
            except Exception as e:
                logger.error('VirtualBox: machine {} not found: {}'
                             .format(machine_obj, e.message))
                return None
        return machine_obj
