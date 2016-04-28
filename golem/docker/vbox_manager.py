import logging
import time
from contextlib import contextmanager
from threading import Thread

import subprocess
from virtualbox import VirtualBox
from virtualbox.library import IMachine, ISession

logger = logging.getLogger(__name__)


class DockerVirtualBoxManager(object):

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

    def __init__(self,
                 default_memory_size=1024,
                 default_cpu_execution_cap=100,
                 default_cpu_count=1,
                 min_memory_size=1024,
                 min_cpu_execution_cap=10,
                 min_cpu_count=1):

        self.api = VirtualBox()
        self.__vm_api_dict = IMachine.__dict__

        self.available = False
        self.docker_images = []
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

    def check_environment(self):
        try:
            # check virtualbox availability
            self.api.version()
            # check docker image availability
            for command in self.docker_vm_list_commands:
                try:
                    output = subprocess.check_output(command)
                    self.docker_images = [i.strip() for i in output.split("\n")]
                    self.available = True
                    return
                except:
                    pass
        except Exception as e:
            logger.warn("VirtualBox: not available - {}"
                        .format(e.message))
        self.available = False

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
            return dict(
                memory_size=vm.memory_size(),
                cpu_count=vm.cpu_count(),
                cpu_execution_cap=vm.cpu_execution_cap()
            )
        except Exception as e:
            logger.error("Virtualbox: error reading VM's constraints: {}"
                         .format(e.message))

    def threaded_constrain_all(self, success, failure, **kwargs):
        total = len(self.docker_images)
        successes = [0]
        failures = [0]
        last_exc = [None]

        def check_total():
            if successes[0] >= total:
                success(self.docker_images)
            elif successes[0] + failures[0] >= total:
                failure(last_exc[0])

        def group_success(*args):
            successes[0] += 1
            check_total()

        def group_failure(exc, *args):
            failures[0] += 1
            last_exc[0] = exc
            check_total()

        return [self.threaded_constrain(image, group_success, group_failure, **kwargs)
                for image in self.docker_images]

    def threaded_constrain(self, name_or_id_or_machine,
                           success, failure, **kwargs):
        def method():
            try:
                self.constrain(name_or_id_or_machine, **kwargs)
                success(name_or_id_or_machine)
            except Exception as e:
                failure(e, name_or_id_or_machine)

        return Thread(target=method)

    def constrain(self, name_or_id_or_machine, **kwargs):
        try:
            self.__constrain(name_or_id_or_machine, **kwargs)
        except Exception as e:
            logger.error("VirtualBox: error setting VM's constraints: {}"
                         .format(e.message))

    def defaults(self, name_or_id_or_machine):
        try:
            self.__constrain(name_or_id_or_machine, **self.defaults)
        except Exception as e:
            logger.error("VirtualBox: error setting VM's defaults: {}"
                         .format(e.message))

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
        logger.debug('Virtualbox: stopping {}'.format())
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

        with self.__restart_ctx(vm, restart=restart):
            self.__apply_constraints(vm, kwargs, force=force)

    def __apply_constraints(self, vm, params, force=False):
        for name, value in params:
            if name in self.__vm_api_dict:
                min_val = self.min_constraints.get(name)

                if force or min_val is None:
                    cur_val = value
                else:
                    cur_val = max(min_val, value)

                try:
                    vm[name](cur_val)
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
