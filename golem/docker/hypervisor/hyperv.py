import logging
from typing import Optional, Union, Any, List, Dict

from os_win.exceptions import OSWinException
from os_win.utils.compute.vmutils import VMUtils

from golem.docker.config import CONSTRAINT_KEYS
from golem.docker.hypervisor.docker_machine import DockerMachineHypervisor

logger = logging.getLogger(__name__)


class HyperVHypervisor(DockerMachineHypervisor):

    DRIVER_NAME = 'hyperv'
    OPTIONS = dict(
        mem='--hyperv-memory',
        cpu='--hyperv-cpu-count',
        disk='--hyperv-disk-size',
        no_virt_mem='--hyperv-disable-dynamic-memory',
        boot2docker_url='--hyperv-boot2docker-url'
    )
    SUMMARY_KEYS = dict(
        mem='MemoryUsage',
        cpu='NumberOfProcessors'
    )
    BOOT2DOCKER_URL = "https://github.com/golemfactory/boot2docker/releases/" \
                      "download/v18.06.0-ce%2Bdvm-v0.35/boot2docker.iso"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._vm_utils = VMUtils()

    def _parse_create_params(
            self,
            cpu: Optional[Union[str, int]] = None,
            mem: Optional[Union[str, int]] = None,
            **params: Any) -> List[str]:

        args = super()._parse_create_params(**params)
        args += [self.OPTIONS['boot2docker_url'], self.BOOT2DOCKER_URL,
                 self.OPTIONS['no_virt_mem']]

        if cpu is not None:
            args += [self.OPTIONS['cpu'], str(cpu)]
        if mem is not None:
            args += [self.OPTIONS['mem'], str(mem)]

        return args

    def constraints(self, name: Optional[str] = None) -> Dict:
        name = name or self._vm_name
        try:
            summary = self._vm_utils.get_vm_summary_info(name)
            return {k: summary[v] for k,v in self.SUMMARY_KEYS.items()}
        except (OSWinException, KeyError):
            logger.exception(
                f'Hyper-V: reading configuration of VM "{name}" failed')
            return {}

    def constrain(self, name: Optional[str] = None, **params) -> None:
        name = name or self._vm_name
        mem = params.get(CONSTRAINT_KEYS['mem'])
        cpu = params.get(CONSTRAINT_KEYS['cpu'])

        try:
            self._vm_utils.update_vm(
                vm_name=name,
                memory_mb=mem,
                memory_per_numa_node=0,
                vcpus_num=cpu,
                vcpus_per_numa_node=0,
                limit_cpu_features=False,
                dynamic_mem_ratio=0
            )
        except OSWinException:
            logger.exception(f'Hyper-V: reconfiguration of VM "{name}" failed')

        logger.info(f'Hyper-V: reconfiguration of VM "{name}" finished')