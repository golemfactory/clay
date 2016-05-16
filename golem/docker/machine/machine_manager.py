import logging
import subprocess
import time
from collections import deque
from contextlib import contextmanager
from threading import Thread

from golem.docker.config_manager import DockerConfigManager

__all__ = ['DockerMachineManager', 'ThreadExecutor']
logger = logging.getLogger(__name__)

FALLBACK_MACHINE_NAME = 'default'


class ThreadExecutor(Thread):
    def __init__(self, group=None, name=None,
                 args=(), kwargs=None, verbose=None):

        super(ThreadExecutor, self).__init__(group, self.loop, name,
                                             args, kwargs, verbose)
        self._threads = deque()
        self.working = True

    def start(self):
        result = super(ThreadExecutor, self).start()

        try:
            from twisted.internet import reactor
            reactor.addSystemEventTrigger("before", "shutdown", self.shutdown)
        except Exception as e:
            logger.warn("Cannot add a shutdown handler: {}"
                        .format(e.message))

        return result

    def loop(self):
        while self.working:
            sleep = 1
            try:
                if self._threads:
                    t = self._threads.popleft()
                    if not t.isAlive():
                        t.start()
                    t.join()
                    sleep = 0.1
            except Exception as e:
                logger.debug("Error executing thread: {}"
                             .format(e.message))
            time.sleep(sleep)

    def push(self, thread):
        total = len(self._threads)
        if total > 1:
            self._threads[-1] = thread
        else:
            self._threads.append(thread)

    def shutdown(self):
        self.working = False


class DockerMachineManager(DockerConfigManager):

    POWER_UP_DOWN_TIMEOUT = 30 * 1000  # milliseconds

    docker_machine_commands = dict(
        active=['docker-machine', 'active'],
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
                 machine_name=None,
                 default_memory_size=1024,
                 default_cpu_execution_cap=100,
                 default_cpu_count=1,
                 min_memory_size=1024,
                 min_cpu_execution_cap=1,
                 min_cpu_count=1):

        self.ISession = None
        self.LockType = None

        self.docker_machine_available = True
        self.docker_machine = machine_name
        self.docker_images = []

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

        self.virtual_box = None
        self.virtual_box_config = self.defaults

        self._env_checked = False
        self._threads = ThreadExecutor()

        if self.docker_machine:
            self.check_environment()

    def check_environment(self):
        logger.debug("DockerManager: checking VM availability")

        try:
            # check VirtualBox availability
            if not self.docker_machine:
                output = self.docker_machine_command('active')
                self.docker_machine = output.strip().replace("\n", "") or \
                                      FALLBACK_MACHINE_NAME
            if not self.docker_machine:
                raise EnvironmentError("Unknown Docker VM name")

            try:

                from virtualbox import VirtualBox
                from virtualbox.library import ISession, LockType

                self.virtual_box = VirtualBox()
                self.ISession = ISession
                self.LockType = LockType

            except ImportError as e:
                raise EnvironmentError("Couldn't import VirtualBox libs: {}"
                                       .format(e.message))

            if not self.virtual_box.version:
                raise EnvironmentError("Cannot connect to VirtualBox")

            # check docker image availability
            self.docker_images = self.__docker_machine_images()
            self.docker_machine_available = True

        except Exception as e:
            logger.warn("DockerMachine: not available: {}".format(e.message))
            self.docker_machine_available = False

        if self.docker_machine_available:
            if self.docker_machine not in self.docker_images:
                logger.warn("DockerMachine: Docker VM {} not available"
                            .format(self.docker_machine))
            elif not self._threads.isAlive():
                self._threads.start()

        self._env_checked = True

    def update_config(self, status_callback, done_callback, in_background=True):
        if not self._env_checked:
            self.check_environment()

        def wait_for_tasks():
            logger.debug("DockerMachine: updating configuration")
            while status_callback():
                time.sleep(0.5)
            self.constrain(self.docker_machine)
            done_callback()

        thread = Thread(target=wait_for_tasks)

        if in_background:
            self._threads.push(thread)
        else:
            thread.run()

    def find_vm(self, name_or_id):
        try:
            return self.virtual_box.find_machine(name_or_id)
        except Exception as e:
            logger.warn("VirtualBox: not available: {}".format(e.message))

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
            logger.error("VirtualBox: error reading VM's constraints: {}"
                         .format(e.message))

    def constrain(self, name_or_id_or_machine, **kwargs):
        constraints = kwargs or self.virtual_box_config

        logger.debug("VirtualBox: starting reconfiguration of '{}'"
                     .format(name_or_id_or_machine))

        try:
            self.__constrain(name_or_id_or_machine, **constraints)
        except Exception as e:
            logger.error("VirtualBox: error setting '{}' VM's constraints: {}"
                         .format(name_or_id_or_machine, e.message))

    def constrain_all(self, images=None, **kwargs):
        try:
            for image_name in images or self.docker_images:
                self.constrain(image_name, **kwargs)
        except Exception as e:
            logger.error("VirtualBox: error constraining images: {}"
                         .format(e.message))

    def build_config(self, config_desc):
        super(DockerMachineManager, self).build_config(config_desc)

        cpu_count = self.min_constraints['cpu_count']
        memory_size = self.min_constraints['memory_size']

        with self._try():
            cpu_count = max(int(config_desc.num_cores), cpu_count)

        with self._try():
            memory_size += int(config_desc.max_memory_size) / 1000

        with self._try():
            if config_desc.docker_machine_name:
                self.docker_machine = config_desc.docker_machine_name
                self._env_checked = False

        self.virtual_box_config = dict(
            memory_size=memory_size,
            cpu_count=cpu_count
        )

    @contextmanager
    def _restart_ctx(self, name_or_id_or_machine, restart=True):
        immutable_vm = self.__machine_from_arg(name_or_id_or_machine)
        if not immutable_vm:
            return

        running = self.__docker_machine_running()
        if running and restart:
            self.__stop_docker_machine()

        session = immutable_vm.create_session(self.LockType.write)
        vm = session.machine
        exception = None

        if str(vm.state) in self.power_down_states:
            self.stop_vm(session)

        try:
            yield vm
        except Exception as e:
            exception = e

        vm.save_settings()

        with self._try():
            session.unlock_machine()
            session.disconnect()

        if restart or not running:
            self.__start_docker_machine()

        if exception:
            logger.error("DockerMachine: restart context error: {}"
                         .format(exception.message))

    def docker_machine_command(self, key, machine_name=None, check_output=True, shell=False):
        command = self.docker_machine_commands.get(key)[:]
        if command:
            if machine_name:
                command += [machine_name]
            if check_output:
                return subprocess.check_output(command, shell=shell)
            return subprocess.check_call(command, shell=shell)
        return ''

    def __docker_machine_running(self):
        if not self.docker_machine:
            raise EnvironmentError("No Docker VM available")

        try:
            status = self.docker_machine_command('status', self.docker_machine)
            status = status.strip().replace("\n", "")
            return status == 'Running'
        except Exception as e:
            logger.error("DockerMachine: failed to check docker-machine status: {}"
                         .format(e.message))
        return False

    def __docker_machine_images(self):
        output = self.docker_machine_command('list')
        if output:
            return [i.strip() for i in output.split("\n") if i]
        raise EnvironmentError("Docker machine images not available")

    def __start_docker_machine(self):
        logger.debug("DockerMachine: starting {}".format(self.docker_machine))

        try:
            self.docker_machine_command('start', self.docker_machine,
                                        check_output=False)
        except Exception as e:
            logger.error("DockerMachine: failed to start the VM: {}"
                         .format(e.message))
        else:
            try:
                docker_images = self.__docker_machine_images()
                if docker_images:
                    self.docker_images = docker_images
            except Exception as e:
                logger.error("DockerMachine: failed to update VM list: {}"
                             .format(e.message))

    def __stop_docker_machine(self):
        logger.debug("DockerMachine: stopping '{}'".format(self.docker_machine))
        try:
            self.docker_machine_command('stop', self.docker_machine,
                                        check_output=False)
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
        force = kwargs.pop('force', False)

        if diff:
            logger.debug("VirtualBox: applying {}".format(diff))

            with self._restart_ctx(vm) as mutable_vm:
                self._apply_constraints(mutable_vm, diff, force=force)
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

    def _apply_constraints(self, vm, params, force=False):
        if not params:
            return

        success = True

        for name, value in params.iteritems():
            min_val = self.min_constraints.get(name)

            if force or min_val is None:
                cur_val = value
            else:
                cur_val = max(min_val, value)

            try:
                setattr(vm, name, cur_val)
            except Exception as e:
                logger.error('VirtualBox: error setting {} to {}: {}'
                             .format(name, value, e.message))
                success = False

        if success:
            logger.debug('VirtualBox: VM {} reconfigured successfully'
                         .format(vm.name))

    def __session_from_arg(self, session_obj, lock_type=None):
        if not isinstance(session_obj, self.ISession):
            vm = self.__machine_from_arg(session_obj)
            lock_type = lock_type or self.LockType.null
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
