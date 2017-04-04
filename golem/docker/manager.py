import json
import logging
import os
import subprocess
import time
from contextlib import contextmanager
from threading import Thread

from golem.core.common import is_linux, is_windows, is_osx, get_golem_path
from golem.core.threads import ThreadQueueExecutor
from golem.docker.config_manager import DockerConfigManager

logger = logging.getLogger(__name__)

ROOT_DIR = get_golem_path()
APPS_DIR = os.path.join(ROOT_DIR, 'apps')
IMAGES_INI = os.path.join(APPS_DIR, 'images.ini')

FALLBACK_DOCKER_MACHINE_NAME = 'golem'
CONSTRAINT_KEYS = dict(
    mem='memory_size',
    cpu='cpu_count',
    cpu_cap='cpu_execution_cap'
)


class DockerManager(DockerConfigManager):

    docker_machine_commands = dict(
        create=['docker-machine', 'create'],
        rm=['docker-machine', 'rm', '-y'],
        start=['docker-machine', 'start'],
        stop=['docker-machine', 'stop'],
        active=['docker-machine', 'active'],
        list=['docker-machine', 'ls', '-q'],
        env=['docker-machine', 'env'],
        status=['docker-machine', 'status'],
        inspect=['docker-machine', 'inspect'],
        regenerate_certs=['docker-machine', 'regenerate-certs']
    )

    docker_commands = dict(
        build=['docker', 'build'],
        tag=['docker', 'tag'],
        pull=['docker', 'pull'],
        version=['docker', '-v'],
        help=['docker', '--help'],
        images=['docker', 'images', '-q']
    )

    def __init__(self, config_desc=None):

        super(DockerManager, self).__init__()

        self.hypervisor = None
        self.docker_machine = FALLBACK_DOCKER_MACHINE_NAME

        self.min_constraints = dict(
            memory_size=1024,
            cpu_execution_cap=1,
            cpu_count=1
        )

        self.defaults = dict(
            memory_size=1024,
            cpu_execution_cap=100,
            cpu_count=1
        )

        self._config = dict(self.defaults)
        self._config_dir = None
        self._env_checked = False
        self._threads = ThreadQueueExecutor(queue_name='docker-machine')

        if config_desc:
            self.build_config(config_desc)

    def _get_hypervisor(self):
        if is_windows():
            return VirtualBoxHypervisor.instance(self)
        elif is_osx():
            return XhyveHypervisor.instance(self)
        return None

    def check_environment(self):

        try:
            # We're checking the availability of "docker" command line utility
            # (other commands may result in an error if docker env variables
            # are set incorrectly)
            self.command('help')
        except Exception as err:
            logger.error(
                """
                ***************************************************************
                Docker is not available, not building images.
                Golem will not be able to compute anything.
                Command 'docker info' returned {}
                ***************************************************************
                """.format(err)
            )
            raise EnvironmentError

        try:
            if is_linux():
                raise EnvironmentError("native Linux environment")

            # Check if a supported VM hypervisor is present
            self.hypervisor = self._get_hypervisor()
            if not self.hypervisor:
                raise EnvironmentError("No supported hypervisor found")

        except Exception as exc:

            self.docker_machine = None
            logger.warn("Docker machine is not available: {}"
                        .format(exc))

        else:

            # Check if DockerMachine VM is present
            if self.docker_machine not in self.docker_machine_images():
                logger.info("Docker machine VM '{}' does not exist"
                            .format(self.docker_machine))

                self.hypervisor.create(self.docker_machine,
                                       **(self._config or self.defaults))

            if not self.docker_machine_running():
                self.start_docker_machine()
            self._set_docker_machine_env()

        try:
            self.pull_images()
        except Exception as exc:
            logger.error("Docker: error pulling images: {}"
                         .format(exc))
            self.build_images()

        self._env_checked = True
        return bool(self.docker_machine)

    def update_config(self, status_callback, done_callback, in_background=True):
        if not self._env_checked:
            self.check_environment()

        if in_background:
            thread = Thread(target=self._wait_for_tasks,
                            args=(status_callback, done_callback))
            self._threads.push(thread)
        else:
            self._wait_for_tasks(status_callback, done_callback)

    def build_config(self, config_desc):
        super(DockerManager, self).build_config(config_desc)

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

        self._config = dict(
            memory_size=memory_size,
            cpu_count=cpu_count
        )

    def constrain(self, name, **params):
        constraints = self.hypervisor.constraints(name)
        diff = self._diff_constraints(constraints, params)

        if diff:

            for constraint, value in diff.iteritems():
                min_val = self.min_constraints.get(constraint)
                diff[constraint] = max(min_val, value)

            for constraint, value in constraints.iteritems():
                if constraint not in diff:
                    diff[constraint] = value

            for constraint, value in self.min_constraints.iteritems():
                if constraint not in diff:
                    diff[constraint] = value

            logger.info("DockerMachine: applying configuration for '{}': {}"
                        .format(name, diff))
            try:
                with self.hypervisor.restart_ctx(name) as vm:
                    self.hypervisor.constrain(vm, **diff)
            except Exception as e:
                logger.error("DockerMachine: error setting '{}' VM's constraints: {}"
                             .format(name, e))
            self._set_docker_machine_env()

        else:

            logger.info("DockerMachine: '{}' configuration unchanged"
                        .format(name))

    def recover_vm_connectivity(self, done_callback, in_background=True):
        """
        This method tries to resolve issues with VirtualBox network adapters (mainly on Windows)
        by saving VM's state and resuming it afterwards with docker-machine. This reestablishes
        SSH connectivity with docker machine VM.
        :param done_callback: Function to run on completion. Takes vbox session as an argument.
        :param in_background: Run the recovery process in a separate thread.
        :return:
        """
        if not self._env_checked:
            self.check_environment()

        if self.docker_machine:
            if in_background:
                thread = Thread(target=self._save_and_resume,
                                args=(done_callback,))
                self._threads.push(thread)
            else:
                self._save_and_resume(done_callback)
        else:
            done_callback()

    def docker_machine_images(self):
        output = self.command('list')
        if output:
            return [i.strip() for i in output.split("\n") if i]
        return []

    def docker_machine_running(self, name=None):
        if not self.docker_machine:
            raise EnvironmentError("No Docker VM available")

        try:
            status = self.command('status', name or self.docker_machine)
            status = status.strip().replace("\n", "")
            return status == 'Running'
        except Exception as e:
            logger.error("DockerMachine: failed to check docker-machine status: {}"
                         .format(e))
        return False

    def start_docker_machine(self, name=None):
        name = name or self.docker_machine
        logger.info("DockerMachine: starting {}".format(name))

        try:
            self.command('start', name, check_output=False)
        except Exception as e:
            logger.error("DockerMachine: failed to start the VM: {}"
                         .format(e))

    def stop_docker_machine(self, name=None):
        name = name or self.docker_machine
        logger.info("DockerMachine: stopping '{}'".format(name))

        try:
            self.command('stop', name, check_output=False)
            return True
        except Exception as e:
            logger.warn("DockerMachine: failed to stop the VM: {}"
                        .format(e))
        return False

    @classmethod
    def command(cls, key, machine_name=None, args=None, check_output=True, shell=False):
        command = cls.docker_machine_commands.get(key)
        if not command:
            command = cls.docker_commands.get(key)
        if not command:
            return ''

        command = command[:]
        if args:
            command += args
        if machine_name:
            command += [machine_name]
        logger.debug('docker_machine_command: %s', command)

        if check_output:
            return subprocess.check_output(command, shell=shell)
        return subprocess.check_call(command)

    @property
    def config_dir(self):
        return self._config_dir

    @classmethod
    def build_images(cls):
        cwd = os.getcwdu()

        for entry in cls._collect_images():
            image, docker_file, tag = entry
            version = '{}:{}'.format(image, tag)

            if not cls.command('images', args=[version],
                               check_output=True):
                try:
                    os.chdir(APPS_DIR)
                    logger.warn('Docker: building image {}'
                                .format(version))
                    cls.command('build', args=['-t', image,
                                               '-f', docker_file,
                                               '.'])
                    cls.command('tag', args=[image, version])
                finally:
                    os.chdir(cwd)

    @classmethod
    def pull_images(cls):
        for entry in cls._collect_images():
            image, docker_file, tag = entry
            version = '{}:{}'.format(image, tag)

            if not cls.command('images', args=[version],
                               check_output=True):

                logger.warn('Docker: pulling image {}'
                            .format(version))
                cls.command('pull', args=[version])

    @classmethod
    def _collect_images(cls):
        images = []
        with open(IMAGES_INI) as f:
            for line in f:
                if line:
                    images.append(line.split())
        return images

    @staticmethod
    def _diff_constraints(old_values, new_values):
        result = dict()

        for key in CONSTRAINT_KEYS.values():
            old_value = old_values.get(key)
            new_value = new_values.get(key)

            if new_value != old_value and new_value is not None:
                result[key] = new_value

        return result

    def _wait_for_tasks(self, sb, cb):
        while sb():
            time.sleep(0.5)
        self.constrain(self.docker_machine, **self._config)
        cb()

    def _save_and_resume(self, cb):
        with self.hypervisor.recover_ctx(self.docker_machine):
            logger.info("DockerMachine: attempting VM recovery")
        self._set_docker_machine_env()
        cb()

    def _set_docker_machine_env(self, retried=False):
        try:
            output = self.command('env', self.docker_machine,
                                  args=('--shell', 'cmd'))
        except subprocess.CalledProcessError:
            if not retried:
                self.command('regenerate_certs', self.docker_machine)
                return self._set_docker_machine_env(retried=True)
            raise

        if output:
            self._set_env_from_output(output)
            logger.info('DockerMachine: env updated')
        else:
            logger.warn('DockerMachine: env update failed')

    def _set_env_from_output(self, output):
        for line in output.split('\n'):
            if not line:
                continue

            cmd, params = line.split(' ', 1)
            if cmd.lower() != 'set':
                continue

            var, val = params.split('=', 1)
            self._set_env_variable(var, val)

            if var == 'DOCKER_CERT_PATH':
                split = val.replace('"', '').split(os.path.sep)
                self._config_dir = os.path.sep.join(split[:-1])

    @staticmethod
    def _set_env_variable(name, value):
        os.environ[name] = value


class Hypervisor(object):

    POWER_UP_DOWN_TIMEOUT = 30 * 1000  # milliseconds
    SAVE_STATE_TIMEOUT = 120 * 1000  # milliseconds

    _instance = None

    def __init__(self, docker_manager):
        self._docker_manager = docker_manager

    @classmethod
    def instance(cls, docker_manager):
        if not cls._instance:
            cls._instance = cls._new_instance(docker_manager)
        return cls._instance

    def create(self, name, **params):
        raise NotImplementedError

    def remove(self, name):
        logger.info("Hypervisor: removing VM '{}'".format(name))
        try:
            self._docker_manager.command('rm', name,
                                         check_output=False)
            return True
        except Exception as e:
            logger.warn("Hypervisor: error removing VM '{}': {}"
                        .format(name, e))
            return False

    def constrain(self, name, **params):
        raise NotImplementedError

    def constraints(self, name):
        raise NotImplementedError

    @contextmanager
    def restart_ctx(self, name):
        raise NotImplementedError

    @contextmanager
    def recover_ctx(self, name):
        raise NotImplementedError

    @classmethod
    def _new_instance(cls, docker_manager):
        raise NotImplementedError


class VirtualBoxHypervisor(Hypervisor):

    power_down_states = [
        'Saved', 'Aborted'
    ]

    running_states = [
        'Running', 'FirstOnline', 'LastOnline'
    ]

    def __init__(self, docker_manager, virtualbox, ISession, LockType):
        super(VirtualBoxHypervisor, self).__init__(None)

        self._docker_manager = docker_manager
        self.virtualbox = virtualbox
        self.ISession = ISession
        self.LockType = LockType

    @contextmanager
    def restart_ctx(self, name):
        immutable_vm = self._machine_from_arg(name)
        if not immutable_vm:
            yield None
            return

        running = self._docker_manager.docker_machine_running()
        if running:
            self._docker_manager.stop_docker_machine()

        session = immutable_vm.create_session(self.LockType.write)
        vm = session.machine

        if str(vm.state) in self.power_down_states:
            self.power_down(session)

        try:
            yield vm
        except Exception as e:
            logger.error("VirtualBox: VM restart error: {}"
                         .format(e))

        vm.save_settings()

        try:
            session.unlock_machine()
        except Exception as e:
            logger.warn("VirtualBox: error unlocking VM '{}': {}"
                        .format(name, e))

        if running:
            self._docker_manager.start_docker_machine()

    @contextmanager
    def recover_ctx(self, name):
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

        self._docker_manager.start_docker_machine()

    def create(self, name, **params):
        logger.info("VirtualBox: creating VM '{}'".format(name))

        try:
            self._docker_manager.command('create', name,
                                         args=('--driver', 'virtualbox'),
                                         check_output=False)
            return True
        except Exception as e:
            logger.error("VirtualBox: error creating VM '{}': {}"
                         .format(name, e))
            return False

    def constraints(self, name):
        result = {}
        try:
            vm = self._machine_from_arg(name)
            for constraint_key in CONSTRAINT_KEYS.values():
                result[constraint_key] = getattr(vm, constraint_key)
        except Exception as e:
            logger.error("VirtualBox: error reading VM's constraints: {}"
                         .format(e))
        return result

    def constrain(self, machine_obj, **params):
        vm = self._machine_from_arg(machine_obj)
        if not vm:
            return

        for name, value in params.iteritems():
            try:
                setattr(vm, name, value)
            except Exception as e:
                logger.error('VirtualBox: error setting {} to {}: {}'
                             .format(name, value, e))

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
        if isinstance(machine_obj, basestring):
            try:
                return self.virtualbox.find_machine(machine_obj)
            except Exception as e:
                logger.error('VirtualBox: machine {} not found: {}'
                             .format(machine_obj, e))
                return None
        return machine_obj

    @classmethod
    def _new_instance(cls, docker_manager):
        try:
            from virtualbox import VirtualBox
            from virtualbox.library import ISession, LockType
        except ImportError:
            return None
        return VirtualBoxHypervisor(docker_manager, VirtualBox(), ISession, LockType)


class XhyveHypervisor(Hypervisor):

    options = dict(
        mem='--xhyve-memory-size',
        cpu='--xhyve-cpu-count',
        disk='--xhyve-disk-size',
        storage='--xhyve-virtio-9p'
    )

    def __init__(self, docker_manager):
        super(XhyveHypervisor, self).__init__(docker_manager)

    def create(self, name, **params):
        cpu = params.get(CONSTRAINT_KEYS['cpu'], None)
        mem = params.get(CONSTRAINT_KEYS['mem'], None)

        args = [
            '--driver', 'xhyve',
            self.options['storage']
        ]

        if cpu is not None:
            args += [self.options['cpu'], str(cpu)]
        if mem is not None:
            args += [self.options['mem'], str(mem)]

        logger.info("Xhyve: creating VM '{}'".format(name))

        try:
            self._docker_manager.command('create', name,
                                         args=args,
                                         check_output=False)
            return True
        except Exception as e:
            logger.error("Xhyve: error creating VM '{}': {}"
                         .format(name, e))
            return False

    def constrain(self, name, **params):
        cpu = params.get(CONSTRAINT_KEYS['cpu'])
        mem = params.get(CONSTRAINT_KEYS['mem'])

        config_path, config = self._config(name)
        if not config:
            return

        try:
            config['Driver'] = config.get('Driver', dict())
            config['Driver']['CPU'] = cpu
            config['Driver']['Memory'] = mem

            with open(config_path, 'w') as config_file:
                config_file.write(json.dumps(config))
        except Exception as e:
            logger.error("Xhyve: error updating '{}' configuration: {}"
                         .format(name, e))

    @contextmanager
    def recover_ctx(self, name):
        with self.restart_ctx(name) as _name:
            yield _name

    @contextmanager
    def restart_ctx(self, name):
        if self._docker_manager.docker_machine_running(name):
            self._docker_manager.stop_docker_machine(name)
        yield name
        self._docker_manager.start_docker_machine(name)

    def constraints(self, name):
        config = dict()

        try:
            output = self._docker_manager.command('inspect', name)
            driver = json.loads(output)['Driver']
        except (TypeError, ValueError) as e:
            logger.error("Xhyve: invalid driver configuration: {}"
                         .format(e))
        else:

            try:
                config[CONSTRAINT_KEYS['cpu']] = int(driver['CPU'])
            except ValueError as e:
                logger.error("Xhyve: error reading CPU count: {}"
                             .format(e))

            try:
                config[CONSTRAINT_KEYS['mem']] = int(driver['Memory'])
            except ValueError as e:
                logger.error("Xhyve: error reading memory size: {}"
                             .format(e))

        return config

    def _config(self, name):
        config_path = os.path.join(self._docker_manager.config_dir, name, 'config.json')
        config = None

        try:
            with open(config_path) as config_file:
                config = json.loads(config_file.read())
        except (IOError, TypeError, ValueError):
            logger.error("Xhyve: error reading '{}' configuration"
                         .format(name))

        return config_path, config

    @classmethod
    def _new_instance(cls, docker_manager):
        return XhyveHypervisor(docker_manager)
