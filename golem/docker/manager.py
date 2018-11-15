import logging
import os
import time
from pathlib import Path
from threading import Thread
from typing import Optional, Callable, Any, Iterable

from golem.core.common import is_linux, is_windows, is_osx
from golem.core.threads import ThreadQueueExecutor
from golem.docker.commands.docker import DockerCommandHandler
from golem.docker.config import DockerConfigManager, APPS_DIR, IMAGES_INI, \
    CONSTRAINT_KEYS, MIN_CONSTRAINTS, DEFAULTS
from golem.docker.hypervisor.docker_for_mac import DockerForMac
from golem.docker.hypervisor.hyperv import HyperVHypervisor
from golem.docker.hypervisor.virtualbox import VirtualBoxHypervisor
from golem.docker.hypervisor.xhyve import XhyveHypervisor
from golem.docker.task_thread import DockerBind
from golem.report import report_calls, Component

logger = logging.getLogger(__name__)


class DockerManager(DockerConfigManager):

    def __init__(self, config_desc=None):
        super().__init__()

        self._config = dict(DEFAULTS)
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
            if HyperVHypervisor.is_available():
                return HyperVHypervisor.instance(self.get_config)
            if VirtualBoxHypervisor.is_available():
                return VirtualBoxHypervisor.instance(self.get_config)
        elif is_osx():
            if DockerForMac.is_available():
                return DockerForMac.instance(self.get_config)
            if XhyveHypervisor.is_available():
                return XhyveHypervisor.instance(self.get_config)
        return None

    def get_config(self) -> dict:
        return dict(self._config)

    def update_config(
            self,
            status_callback: Callable[[], Any],
            done_callback: Callable[[bool], Any],
            work_dir: Path,
            in_background: bool = True
    ) -> None:
        self.check_environment()

        if self.hypervisor:
            self.hypervisor.update_work_dir(work_dir)

        if in_background:
            thread = Thread(target=self._wait_for_tasks,
                            args=(status_callback, done_callback))
            self._threads.push(thread)
        else:
            self._wait_for_tasks(status_callback, done_callback)

    def build_config(self, config_desc):
        super(DockerManager, self).build_config(config_desc)

        cpu_count = MIN_CONSTRAINTS['cpu_count']
        memory_size = MIN_CONSTRAINTS['memory_size']

        try:
            cpu_count = max(int(config_desc.num_cores), cpu_count)
        except (TypeError, ValueError) as exc:
            logger.warning('Cannot read the CPU count: %r', exc)

        try:
            memory_size = max(int(config_desc.max_memory_size) // 1024,
                              memory_size)
            # Hyper-V expects a multiple of 2 MB
            memory_size = memory_size // 2 * 2
        except (TypeError, ValueError) as exc:
            logger.warning('Cannot read the memory amount: %r', exc)

        self._config = dict(
            memory_size=memory_size,
            cpu_count=cpu_count
        )

    def get_host_config_for_task(self, binds: Iterable[DockerBind]) -> dict:
        host_config = dict(self._container_host_config)
        if self.hypervisor and self.hypervisor.uses_volumes():
            host_config['binds'] = self.hypervisor.create_volumes(binds)
        else:
            host_config['binds'] = {
                str(bind.source): {
                    'bind': bind.target,
                    'mode': bind.mode
                }
                for bind in binds
            }
        return host_config

    def constrain(self, **params) -> bool:
        if not self.hypervisor:
            return False

        constraints = self.hypervisor.constraints()
        diff = self._diff_constraints(constraints, params)

        if diff:

            for constraint, value in diff.items():
                min_val = MIN_CONSTRAINTS.get(constraint)
                diff[constraint] = max(min_val, value)

            for constraint, value in constraints.items():
                if constraint not in diff:
                    diff[constraint] = value

            for constraint, value in MIN_CONSTRAINTS.items():
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
        This method tries to resolve issues with VirtualBox network adapters
        (mainly on Windows) by saving VM's state and resuming it afterwards with
        docker-machine. This reestablishes SSH connectivity with docker machine
        VM.
        :param done_callback: Function to run on completion. Takes vbox session
        as an argument.
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

    @staticmethod
    def command(*args, **kwargs) -> Optional[str]:
        kwargs.pop('machine_name', None)
        return DockerCommandHandler.run(*args, **kwargs)

    def build_images(self):
        entries = []

        for entry in self._collect_images():
            version = self._image_version(entry)

            if not self._image_supported(entry):
                logger.warning('Image %s is not supported', version)
                continue

            if not self.command('images', args=[version]):
                entries.append(entry)

        if entries:
            self._build_images(entries)

    @report_calls(Component.docker, 'images.build')
    def _build_images(self, entries):
        cwd = os.getcwd()

        for entry in entries:
            image, docker_file, _, build_dir = entry[:4]
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

            if not self._image_supported(entry):
                logger.warning('Image %s is not supported', version)
                continue

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
        image, _, tag = entry[:3]
        return '{}:{}'.format(image, tag)

    @classmethod
    def _image_supported(cls, entry):
        if len(entry) < 5:
            return True

        from importlib import import_module

        try:
            path = entry[4]
            package, name = path.rsplit('.', 1)
            module = import_module(package)
            is_supported = getattr(module, name)
        except (AttributeError, TypeError, ModuleNotFoundError, ImportError):
            return False
        else:
            return is_supported(entry[0])

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
        if self.hypervisor:
            with self.hypervisor.recover_ctx():
                logger.info("DockerMachine: attempting VM recovery")
        cb()
