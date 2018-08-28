import json
import logging
import os
from contextlib import contextmanager
from typing import Dict, Optional

from golem.docker.config import CONSTRAINT_KEYS
from golem.docker.hypervisor.docker_machine import DockerMachineHypervisor
from golem.report import Component, report_calls

logger = logging.getLogger(__name__)


class XhyveHypervisor(DockerMachineHypervisor):

    options = dict(
        mem='--xhyve-memory-size',
        cpu='--xhyve-cpu-count',
        disk='--xhyve-disk-size',
        storage='--xhyve-virtio-9p'
    )

    @report_calls(Component.hypervisor, 'vm.create')
    def create(self, name: Optional[str] = None, **params):
        name = name or self._vm_name
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
            self.command('create', name, args=args)
            return True
        except Exception as e:
            logger.error("Xhyve: error creating VM '{}': {}"
                         .format(name, e))
            return False

    def constrain(self, name: Optional[str] = None, **params) -> None:
        name = name or self._vm_name
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

    def constraints(self, name: Optional[str] = None) -> Dict:
        name = name or self._vm_name
        config = dict()

        try:
            output = self.command('inspect', name) or ''
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
