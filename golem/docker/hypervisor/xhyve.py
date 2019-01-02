import json
import logging
import os
from typing import Dict, Optional, Any, List, Union, ClassVar

from golem.docker.config import CONSTRAINT_KEYS
from golem.docker.hypervisor.docker_machine import DockerMachineHypervisor

logger = logging.getLogger(__name__)


class XhyveHypervisor(DockerMachineHypervisor):

    DRIVER_NAME: ClassVar[str] = 'xhyve'
    OPTIONS = dict(
        mem='--xhyve-memory-size',
        cpu='--xhyve-cpu-count',
        disk='--xhyve-disk-size',
        storage='--xhyve-virtio-9p'
    )

    # pylint: disable=arguments-differ
    def _parse_create_params(
            self,
            cpu: Optional[int] = None,
            mem: Optional[int] = None,
            **params: Any) -> List[str]:

        args = super()._parse_create_params(**params)
        args += [self.OPTIONS['storage']]

        if cpu is not None:
            args += [self.OPTIONS['cpu'], str(cpu)]
        if mem is not None:
            args += [self.OPTIONS['mem'], str(mem)]

        return args

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
