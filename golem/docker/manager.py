import json
import logging
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from threading import Thread
from typing import List, Optional, Dict

from golem.core.common import is_linux, is_windows, is_osx, get_golem_path
from golem.core.threads import ThreadQueueExecutor
from golem.docker.commands import DockerCommandHandler, CommandDict
from golem.docker.config import DockerConfigManager
from golem.report import report_calls, Component

logger = logging.getLogger(__name__)

ROOT_DIR = get_golem_path()
APPS_DIR = os.path.join(ROOT_DIR, 'apps')
IMAGES_INI = os.path.join(APPS_DIR, 'images.ini')

DOCKER_VM_NAME = 'golem'
CONSTRAINT_KEYS = dict(
    mem='memory_size',
    cpu='cpu_count',
    cpu_cap='cpu_execution_cap'
)


class DockerMachineCommandHandler(DockerCommandHandler):

    commands: CommandDict = dict(
        create=['docker-machine', 'create'],
        rm=['docker-machine', 'rm', '-y'],
        start=['docker-machine', 'restart'],
        stop=['docker-machine', 'stop'],
        active=['docker-machine', 'active'],
        list=['docker-machine', 'ls', '-q'],
        env=['docker-machine', 'env'],
        status=['docker-machine', 'status'],
        inspect=['docker-machine', 'inspect'],
        regenerate_certs=['docker-machine', 'regenerate-certs', '--force']
    )

    commands.update(DockerCommandHandler.commands)


class DockerManager(DockerConfigManager):

    def __init__(self, config_desc=None):
        super(DockerManager, self).__init__()

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
        self._env_checked = False
        self._threads = ThreadQueueExecutor(queue_name='docker-machine')

        if config_desc:
            self.build_config(config_desc)

    @report_calls(Component.docker, 'instance.check')
    def check_environment(self):
        if self._env_checked:
            return bool(self.hypervisor)

        self._env_checked = True

        try:
            if not is_linux():
                self.hypervisor = self._select_hypervisor()
                self.hypervisor.setup()
        except Exception:  # pylint: disable=broad-except
            logger.error(
                """
                ***************************************************************
                No supported VM hypervisor was found.
                Golem will not be able to compute anything.
                ***************************************************************
                """
            )
            raise EnvironmentError

        try:
            # We're checking the availability of "docker" command line utility
            # (other commands may result in an error if docker env variables
            # are set incorrectly)
            self.command('help')
        except Exception as err:  # pylint: disable=broad-except
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
            self.pull_images()
        except Exception as err:  # pylint: disable=broad-except
            logger.warning("Docker: error pulling images: %r", err)
            self.build_images()

        return bool(self.hypervisor)

    def _select_hypervisor(self):
        if is_windows():
            return VirtualBoxHypervisor.instance(self)
        elif is_osx():
            if DockerForMac.is_available():
                return DockerForMac.instance(self)
            return XhyveHypervisor.instance(self)
        return None

    @property
    def config(self) -> dict:
        return dict(self._config)

    def update_config(self, status_callback, done_callback, in_background=True):
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

        try:
            cpu_count = max(int(config_desc.num_cores), cpu_count)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning('Cannot read the CPU count: %r', exc)

        try:
            memory_size = max(int(config_desc.max_memory_size) // 1024,
                              memory_size)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning('Cannot read the memory amount: %r', exc)

        self._config = dict(
            memory_size=memory_size,
            cpu_count=cpu_count
        )

    def constrain(self, **params) -> bool:
        if not self.hypervisor:
            return False

        constraints = self.hypervisor.constraints()
        diff = self._diff_constraints(constraints, params)

        if diff:

            for constraint, value in diff.items():
                min_val = self.min_constraints.get(constraint)
                diff[constraint] = max(min_val, value)

            for constraint, value in constraints.items():
                if constraint not in diff:
                    diff[constraint] = value

            for constraint, value in self.min_constraints.items():
                if constraint not in diff:
                    diff[constraint] = value

            logger.info("Docker: applying configuration: %r", diff)
            try:
                with self.hypervisor.restart_ctx() as vm:
                    self.hypervisor.constrain(vm, **diff)
            except Exception as e:
                logger.error("Docker: error updating configuration: %r", e)

        else:

            logger.info("Docker: configuration unchanged")

        return bool(diff)

    def recover_vm_connectivity(self, done_callback, in_background=True):
        """
        This method tries to resolve issues with VirtualBox network adapters (mainly on Windows)
        by saving VM's state and resuming it afterwards with docker-machine. This reestablishes
        SSH connectivity with docker machine VM.
        :param done_callback: Function to run on completion. Takes vbox session as an argument.
        :param in_background: Run the recovery process in a separate thread.
        :return:
        """
        self.check_environment()

        if self.hypervisor:
            if in_background:
                thread = Thread(target=self._save_and_resume,
                                args=(done_callback,))
                self._threads.push(thread)
            else:
                self._save_and_resume(done_callback)
        else:
            done_callback()

    def command(self, key, machine_name=None, args=None, shell=False):
        args = key, machine_name, args, shell
        if self.hypervisor:
            return self.hypervisor.COMMAND_HANDLER.run(*args)
        return DockerCommandHandler.run(*args)

    def build_images(self):
        entries = []

        for entry in self._collect_images():
            version = self._image_version(entry)
            if not self.command('images', args=[version]):
                entries.append(entry)

        if entries:
            self._build_images(entries)

    @report_calls(Component.docker, 'images.build')
    def _build_images(self, entries):
        cwd = os.getcwd()

        for entry in entries:
            image, docker_file, tag, build_dir = entry
            version = self._image_version(entry)

            try:
                os.chdir(APPS_DIR)
                logger.warning('Docker: building image %s', version)

                self.command('build', args=['-t', image,
                                            '-f', docker_file,
                                            build_dir])
                self.command('tag', args=[image, version])
            finally:
                os.chdir(cwd)

    def pull_images(self):
        entries = []

        for entry in self._collect_images():
            version = self._image_version(entry)
            if not self.command('images', args=[version]):
                entries.append(entry)

        if entries:
            self._pull_images(entries)

    def _pull_images(self, entries):
        for entry in entries:
            version = self._image_version(entry)
            self._pull_image(version)

    @report_calls(Component.docker, 'images.pull')
    def _pull_image(self, version):
        logger.warning('Docker: pulling image %r', version)
        self.command('pull', args=[version])

    @classmethod
    def _image_version(cls, entry):
        image, _, tag, _ = entry
        return '{}:{}'.format(image, tag)

    @classmethod
    def _collect_images(cls):
        with open(IMAGES_INI) as f:
            return [line.split() for line in f if line]

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

        config_differs = self.constrain(**self._config)
        cb(config_differs)

    def _save_and_resume(self, cb):
        with self.hypervisor.recover_ctx():
            logger.info("DockerMachine: attempting VM recovery")
        cb()


class Hypervisor(object):

    POWER_UP_DOWN_TIMEOUT = 30 * 1000  # milliseconds
    SAVE_STATE_TIMEOUT = 120 * 1000  # milliseconds
    COMMAND_HANDLER = DockerCommandHandler

    _instance = None

    def __init__(self, docker_manager: DockerManager,
                 docker_vm: str = DOCKER_VM_NAME) -> None:
        self._docker_manager = docker_manager
        self._docker_vm = docker_vm

    @classmethod
    def is_available(cls):
        return True

    def setup(self) -> None:
        if not self.vm_running():
            self.start_vm()

    @classmethod
    def instance(cls, docker_manager):
        if not cls._instance:
            cls._instance = cls._new_instance(docker_manager)
        return cls._instance

    def create(self, name: Optional[str] = None, **params):
        raise NotImplementedError

    def remove(self, name: Optional[str] = None) -> bool:
        logger.info("Hypervisor: removing VM '%s'", name)
        try:
            self._docker_manager.command('rm', name)
            return True
        except subprocess.CalledProcessError as e:
            logger.warning("Hypervisor: error removing VM '%s': %s", name, e)
            logger.debug("Hypervisor_output: %s", e.output)
        return False

    @report_calls(Component.docker, 'instance.check')
    def vm_running(self, name: Optional[str] = None) -> bool:
        name = name or self._docker_vm
        if not name:
            raise EnvironmentError("Invalid Docker VM name")

        try:
            status = self._docker_manager.command('status', name)
            status = status.strip().replace("\n", "")
            return status == 'Running'
        except subprocess.CalledProcessError as e:
            logger.error("DockerMachine: failed to check status: %s", e)
        return False

    @report_calls(Component.docker, 'instance.start')
    def start_vm(self, name: Optional[str] = None) -> None:
        name = name or self._docker_vm
        logger.info("Docker: starting VM %s", name)

        try:
            self._docker_manager.command('start', name)
        except subprocess.CalledProcessError as e:
            logger.error("Docker: failed to start the VM: %r", e)
            raise

    @report_calls(Component.docker, 'instance.stop')
    def stop_vm(self, name: Optional[str] = None) -> bool:
        name = name or self._docker_vm
        logger.info("Docker: stopping %s", name)

        try:
            self._docker_manager.command('stop', name)
            return True
        except subprocess.CalledProcessError as e:
            logger.warning("Docker: failed to stop the VM: %r", e)
        return False

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

    @classmethod
    def _new_instance(cls,
                      docker_manager: DockerManager) -> Optional['Hypervisor']:
        raise NotImplementedError


class DockerMachineHypervisor(Hypervisor):

    COMMAND_HANDLER = DockerMachineCommandHandler

    def __init__(self, docker_manager: DockerManager) -> None:
        super().__init__(docker_manager)
        self._config_dir = None

    def setup(self) -> None:
        if self._docker_vm not in self.vms:
            logger.info("Creating Docker VM '%r'", self._docker_vm)
            self.create(self._docker_vm, **self._docker_manager.config)

        if not self.vm_running():
            self.start_vm()
        self._set_env()

    @property
    def vms(self):
        output = self._docker_manager.command('list')
        if output:
            return [i.strip() for i in output.split("\n") if i]
        return []

    @property
    def config_dir(self):
        return self._config_dir

    @report_calls(Component.docker, 'instance.env')
    def _set_env(self, retried=False):
        try:
            output = self._docker_manager.command('env', self._docker_vm,
                                                  args=('--shell', 'cmd'))
        except subprocess.CalledProcessError as e:
            logger.warning("DockerMachine: failed to env the VM: %s", e)
            logger.debug("DockerMachine_output: %s", e.output)
            if not retried:
                return self._recover()
            typical_solution_s = """It seems there is a  problem with your Docker installation.
Ensure that you try the following before reporting an issue:

 1. The virtualization of Intel VT-x/EPT or AMD-V/RVI is enabled in BIOS
    or virtual machine settings.
 2. The proper environment is set. On windows powershell please run:
    & "C:\Program Files\Docker Toolbox\docker-machine.exe" env golem | Invoke-Expression
 3. virtualbox driver is available:
    docker-machine.exe create --driver virtualbox golem
 4. Restart Windows machine"""
            logger.error(typical_solution_s)
            raise

        if output:
            self._set_env_from_output(output)
            logger.info('DockerMachine: env updated')
        else:
            logger.warning('DockerMachine: env update failed')

    def _recover(self):
        try:
            self._docker_manager.command('regenerate_certs', self._docker_vm)
        except subprocess.CalledProcessError as e:
            logger.warning("DockerMachine:"
                           " failed to env the VM: %s -- %s",
                           e, e.output)
        else:
            return self._set_env(retried=True)

        try:
            self._docker_manager.command('start', self._docker_vm)
        except subprocess.CalledProcessError as e:
            logger.warning("DockerMachine:"
                           " failed to restart the VM: %s -- %s",
                           e, e.output)
        else:
            return self._set_env(retried=True)

        try:
            if self.remove(self._docker_vm):
                self.create(self._docker_vm)
        except subprocess.CalledProcessError as e:
            logger.warning("DockerMachine:"
                           " failed to re-create the VM: %s -- %s",
                           e, e.output)

        return self._set_env(retried=True)

    def _set_env_from_output(self, output):
        for line in output.split('\n'):
            if not line:
                continue

            cmd, params = line.split(' ', 1)
            if cmd.lower() != 'set':
                continue

            var, val = params.split('=', 1)
            os.environ[var] = val

            if var == 'DOCKER_CERT_PATH':
                split = val.replace('"', '').split(os.path.sep)
                self._config_dir = os.path.sep.join(split[:-1])

    def create(self, name: Optional[str] = None, **params):
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

    @classmethod
    def _new_instance(cls,
                      docker_manager: DockerManager) -> Optional['Hypervisor']:
        raise NotImplementedError


class VirtualBoxHypervisor(DockerMachineHypervisor):

    power_down_states = [
        'Saved', 'Aborted'
    ]

    running_states = [
        'Running', 'FirstOnline', 'LastOnline'
    ]

    def __init__(self, docker_manager, virtualbox, ISession, LockType):
        super(VirtualBoxHypervisor, self).__init__(docker_manager)

        if is_windows():
            import pythoncom  # noqa # pylint: disable=import-error
            pythoncom.CoInitialize()

        self.virtualbox = virtualbox
        self.ISession = ISession
        self.LockType = LockType

    @contextmanager
    @report_calls(Component.hypervisor, 'vm.restart')
    def restart_ctx(self, name: Optional[str] = None):
        name = name or self._docker_vm
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
        name = name or self._docker_vm
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

    @report_calls(Component.hypervisor, 'vm.create')
    def create(self, name: Optional[str] = None, **params) -> bool:
        logger.info("VirtualBox: creating VM '{}'".format(name))

        try:
            self._docker_manager.command('create', name,
                                         args=('--driver', 'virtualbox'))
            return True
        except subprocess.CalledProcessError as e:
            logger.error("VirtualBox: error creating VM '%s': %s", name, e)
            logger.debug("Hypervisor_output: %s", e.output)
        return False

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
                      docker_manager: DockerManager) -> Optional[Hypervisor]:
        try:
            from virtualbox import VirtualBox
            from virtualbox.library import ISession, LockType
        except ImportError:
            return None
        return VirtualBoxHypervisor(docker_manager, VirtualBox(),
                                    ISession, LockType)


class XhyveHypervisor(DockerMachineHypervisor):

    options = dict(
        mem='--xhyve-memory-size',
        cpu='--xhyve-cpu-count',
        disk='--xhyve-disk-size',
        storage='--xhyve-virtio-9p'
    )

    def __init__(self, docker_manager):
        super(XhyveHypervisor, self).__init__(docker_manager)

    @report_calls(Component.hypervisor, 'vm.create')
    def create(self, name: Optional[str] = None, **params):
        name = name or self._docker_vm
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
                                         args=args)
            return True
        except Exception as e:
            logger.error("Xhyve: error creating VM '{}': {}"
                         .format(name, e))
            return False

    def constrain(self, name: Optional[str] = None, **params) -> None:
        name = name or self._docker_vm
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
    @report_calls(Component.hypervisor, 'vm.recover')
    def recover_ctx(self, name: Optional[str] = None):
        name = name or self._docker_vm
        with self.restart_ctx(name) as _name:
            yield _name
        self._set_env()

    @contextmanager
    @report_calls(Component.hypervisor, 'vm.restart')
    def restart_ctx(self, name: Optional[str] = None):
        name = name or self._docker_vm
        if self.vm_running(name):
            self.stop_vm(name)
        yield name
        self.start_vm(name)
        self._set_env()

    def constraints(self, name: Optional[str] = None) -> Dict:
        name = name or self._docker_vm
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
        config_path = os.path.join(self._config_dir, name, 'config.json')
        config = None

        try:
            with open(config_path) as config_file:
                config = json.loads(config_file.read())
        except (IOError, TypeError, ValueError):
            logger.error("Xhyve: error reading '{}' configuration"
                         .format(name))

        return config_path, config

    @classmethod
    def _new_instance(cls,
                      docker_manager: DockerManager) -> Optional[Hypervisor]:
        return XhyveHypervisor(docker_manager)


class DockerForMacCommandHandler(DockerCommandHandler):

    APP = '/Applications/Docker.app'
    PROCESSES = {
        'app': f'{APP}/Contents/MacOS/Docker',
        'driver': 'com.docker.driver',
        'hyperkit': 'com.docker.hyperkit',
        'vpnkit': 'com.docker.vpnkit',
    }

    @classmethod
    def start(cls, *_args, **_kwargs) -> None:
        try:
            subprocess.check_call(['open', '-g', '-a', cls.PROCESSES['app']])
            cls.wait_until_started()
        except subprocess.CalledProcessError:
            logger.error('Docker for Mac: unable to start the app')
            sys.exit(1)

    @classmethod
    def stop(cls) -> None:
        pid = cls._pid()
        if not pid:
            return

        try:
            subprocess.check_call(['kill', str(pid)])
        except subprocess.CalledProcessError:
            return

        cls.wait_until_stopped()

    @classmethod
    def status(cls) -> str:
        return 'Running' if cls._pid() else ''

    @classmethod
    def wait_until_stopped(cls):
        started = time.time()

        while any(map(cls._pid, cls.PROCESSES)):
            if time.time() - started >= cls.TIMEOUT:
                logger.error('Docker for Mac: VM start timeout')
                return
            time.sleep(0.5)

    @classmethod
    def _pid(cls, key: str = 'app') -> Optional[int]:

        process_name = cls.PROCESSES[key]
        process_name = f'[{process_name[0]}]{process_name[1:]}'

        try:
            line = cls._pipe(['ps', 'ux'], ['grep', '-i', process_name])
        except subprocess.CalledProcessError:
            return None

        try:
            return int(line.split()[1])
        except (IndexError, TypeError, ValueError):
            return None

    @staticmethod
    def _pipe(cmd: List[str], pipe: List[str]):
        proc_cmd = subprocess.Popen(cmd,
                                    stdout=subprocess.PIPE)
        proc_pipe = subprocess.Popen(pipe,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     stdin=proc_cmd.stdout)
        proc_cmd.stdout.close()
        stdout, _ = proc_pipe.communicate()
        return stdout.strip().decode('utf-8')

    # pylint: disable=undefined-variable
    commands: CommandDict = dict(
        start=lambda *_: DockerForMacCommandHandler.start(),
        stop=lambda *_: DockerForMacCommandHandler.stop(),
        status=lambda *_: DockerForMacCommandHandler.status(),
    )

    commands.update(DockerCommandHandler.commands)


class DockerForMac(Hypervisor):
    """ Implements Docker for Mac integration as a hypervisor. """

    COMMAND_HANDLER = DockerForMacCommandHandler

    CONFIG_FILE = os.path.expanduser(
        "~/Library/Group Containers/group.com.docker/settings.json"
    )

    def setup(self) -> None:
        if self.vm_running():
            # wait until Docker is ready
            self.COMMAND_HANDLER.wait_until_started()
        else:
            self.start_vm()

    @classmethod
    def is_available(cls):
        return os.path.exists(cls.COMMAND_HANDLER.APP)

    def create(self, name: Optional[str] = None, **params) -> bool:
        # We do not control VM creation
        return False

    def remove(self, name: Optional[str] = None) -> bool:
        # We do not control VM removal
        return False

    def constrain(self, name: Optional[str] = None, **params) -> None:
        cpu = params.get(CONSTRAINT_KEYS['cpu'])
        mem = params.get(CONSTRAINT_KEYS['mem'])
        update = dict(cpus=cpu, memoryMiB=mem)

        try:
            self._update_config(update)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Docker for Mac: unable to update config: %r", e)

    def constraints(self, name: Optional[str] = None) -> Dict:
        if not os.path.exists(self.CONFIG_FILE):
            self.start_vm()
        if not os.path.exists(self.CONFIG_FILE):
            raise RuntimeError('Docker for Mac: unable to read VM config')

        with open(self.CONFIG_FILE) as config_file:
            config = json.load(config_file)

        constraints = dict()

        try:
            constraints[CONSTRAINT_KEYS['cpu']] = int(config['cpus'])
        except (KeyError, ValueError) as e:
            logger.error("Docker for Mac: error reading CPU count: %r", e)

        try:
            constraints[CONSTRAINT_KEYS['mem']] = int(config['memoryMiB'])
        except (KeyError, ValueError) as e:
            logger.error("Docker for Mac: error reading memory size: %r", e)

        return constraints

    def _update_config(self, update: Dict) -> None:
        with open(self.CONFIG_FILE) as config_file:
            config = json.load(config_file)

        config.update(update)

        with open(self.CONFIG_FILE, 'w') as config_file:
            json.dump(config, config_file)

    @contextmanager
    @report_calls(Component.hypervisor, 'vm.restart')
    def restart_ctx(self, name: Optional[str] = None):
        if self.vm_running():
            self.stop_vm()
        yield name
        self.start_vm()

    @contextmanager
    @report_calls(Component.hypervisor, 'vm.recover')
    def recover_ctx(self, name: Optional[str] = None):
        self.restart_ctx(name)

    @classmethod
    def _new_instance(cls,
                      docker_manager: DockerManager) -> Optional[Hypervisor]:
        return DockerForMac(docker_manager)
