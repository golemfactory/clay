import logging
import os
import subprocess
from abc import ABCMeta
from contextlib import contextmanager
from typing import Optional, ClassVar, Any, List

from golem.docker.commands.docker_machine import DockerMachineCommandHandler
from golem.docker.config import DOCKER_VM_NAME, GetConfigFunction, \
    CONSTRAINT_KEYS
from golem.docker.hypervisor import Hypervisor
from golem.report import Component, report_calls

logger = logging.getLogger(__name__)


class DockerMachineHypervisor(Hypervisor, metaclass=ABCMeta):

    COMMAND_HANDLER = DockerMachineCommandHandler
    DRIVER_PARAM_NAME = "--driver"
    DRIVER_NAME: ClassVar[str]

    def __init__(self,
                 get_config_fn: GetConfigFunction,
                 vm_name: str = DOCKER_VM_NAME) -> None:
        super().__init__(get_config_fn, vm_name)
        self._config_dir = None

    def setup(self) -> None:
        if self._vm_name not in self.vms:
            logger.info("Creating Docker VM '%r'", self._vm_name)
            self.create(self._vm_name, **self._get_config())

        if not self.vm_running():
            self.start_vm()
        self._set_env()

    def _parse_create_params(self, **params: Any) -> List[str]:
        return [self.DRIVER_PARAM_NAME, self.DRIVER_NAME]

    @report_calls(Component.hypervisor, 'vm.create')
    def create(self, vm_name: Optional[str] = None, **params) -> bool:
        vm_name = vm_name or self._vm_name
        constraints = {
            k: params.pop(v, None)
            for k, v in CONSTRAINT_KEYS.items()
        }
        command_args = self._parse_create_params(**constraints, **params)

        logger.info(f'{self.DRIVER_NAME}: creating VM "{vm_name}"')

        try:
            self.command('create', vm_name, args=command_args)
            return True
        except subprocess.CalledProcessError as e:
            logger.exception(
                f'{self.DRIVER_NAME}: error creating VM "{vm_name}"')
            logger.debug(f'Hypervisor output: {e.output}')
            return False

    @contextmanager
    @report_calls(Component.hypervisor, 'vm.recover')
    def recover_ctx(self, name: Optional[str] = None):
        name = name or self._vm_name
        with self.restart_ctx(name) as _name:
            yield _name
        self._set_env()

    @contextmanager
    @report_calls(Component.hypervisor, 'vm.restart')
    def restart_ctx(self, name: Optional[str] = None):
        name = name or self._vm_name
        if self.vm_running(name):
            self.stop_vm(name)
        yield name
        self.start_vm(name)
        self._set_env()

    @property
    def vms(self):
        try:
            output = self.command('list')
        except subprocess.CalledProcessError as e:
            logger.warning("DockerMachine: failed to list VMs: %r", e)
        else:
            if output:
                return [i.strip() for i in output.split("\n") if i]
        return []

    @property
    def config_dir(self):
        return self._config_dir

    @report_calls(Component.docker, 'instance.env')
    def _set_env(self, retried=False):
        try:
            output = self.command('env', self._vm_name,
                                  args=('--shell', 'cmd'))
        except subprocess.CalledProcessError as e:
            logger.warning("DockerMachine: failed to update env for VM: %s", e)
            logger.debug("DockerMachine_output: %s", e.output)
            if not retried:
                return self._recover()
            typical_solution_s = \
                """It seems there is a  problem with your Docker installation.
Ensure that you try the following before reporting an issue:

 1. The virtualization of Intel VT-x/EPT or AMD-V/RVI is enabled in BIOS
    or virtual machine settings.
 2. The proper environment is set. On windows powershell please run:
    & "C:\Program Files\Docker Toolbox\docker-machine.exe" ^
    env golem | Invoke-Expression
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
            self.command('regenerate_certs', self._vm_name)
        except subprocess.CalledProcessError as e:
            logger.warning("DockerMachine:"
                           " failed to env the VM: %s -- %s",
                           e, e.output)
        else:
            return self._set_env(retried=True)

        try:
            self.command('start', self._vm_name)
        except subprocess.CalledProcessError as e:
            logger.warning("DockerMachine:"
                           " failed to restart the VM: %s -- %s",
                           e, e.output)
        else:
            return self._set_env(retried=True)

        try:
            if self.remove(self._vm_name):
                self.create(self._vm_name)
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
