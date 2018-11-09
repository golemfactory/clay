import logging
import os
from pathlib import Path
import subprocess
from subprocess import CalledProcessError, TimeoutExpired
from typing import Optional, Union, Any, List, Dict, ClassVar, Iterable

from os_win.exceptions import OSWinException
from os_win.utils import _wqlutils
from os_win.utils.compute.vmutils import VMUtils

from golem.core.common import get_golem_path
from golem.docker import smbshare
from golem.docker.client import local_client
from golem.docker.config import CONSTRAINT_KEYS, MIN_CONSTRAINTS
from golem.docker.hypervisor.docker_machine import DockerMachineHypervisor
from golem.docker.task_thread import DockerBind

logger = logging.getLogger(__name__)


class HyperVHypervisor(DockerMachineHypervisor):

    DRIVER_NAME: ClassVar[str] = 'hyperv'
    OPTIONS = dict(
        mem='--hyperv-memory',
        cpu='--hyperv-cpu-count',
        disk='--hyperv-disk-size',
        boot2docker_url='--hyperv-boot2docker-url',
        virtual_switch='--hyperv-virtual-switch'
    )
    BOOT2DOCKER_URL = "https://github.com/golemfactory/boot2docker/releases/" \
                      "download/v18.06.1-ce%2Bdvn-v0.35/boot2docker.iso"
    DOCKER_USER = "golem-docker"
    DOCKER_PASSWORD = "golem-docker"
    VOLUME_DRIVER = "cifs"

    GET_VSWITCH_SCRIPT_PATH = \
        os.path.join(get_golem_path(), 'scripts', 'get-default-vswitch.ps1')
    SCRIPT_TIMEOUT = 5  # seconds

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._vm_utils = VMUtils()

    # pylint: disable=arguments-differ
    def _parse_create_params(
            self,
            cpu: Optional[Union[str, int]] = None,
            mem: Optional[Union[str, int]] = None,
            **params: Any) -> List[str]:

        args = super()._parse_create_params(**params)
        virtual_switch = self._get_vswitch_name()
        args += [self.OPTIONS['boot2docker_url'], self.BOOT2DOCKER_URL,
                 self.OPTIONS['virtual_switch'], virtual_switch]

        if cpu is not None:
            args += [self.OPTIONS['cpu'], str(cpu)]
        if mem is not None:
            args += [self.OPTIONS['mem'], str(mem)]

        return args

    def constraints(self, name: Optional[str] = None) -> Dict:
        name = name or self._vm_name
        try:
            summary = self._vm_utils.get_vm_summary_info(name)
            mem_settings = self._vm_utils.get_vm_memory_info(name)
            logger.debug('raw hyperv info: summary=%r, memory=%r',
                         summary, mem_settings)
            result = dict()
            result[CONSTRAINT_KEYS['mem']] = mem_settings['Limit']
            result[CONSTRAINT_KEYS['cpu']] = summary['NumberOfProcessors']
            return result
        except (OSWinException, KeyError):
            logger.exception(
                f'Hyper-V: reading configuration of VM "{name}" failed')
            return {}

    def constrain(self, name: Optional[str] = None, **params) -> None:
        name = name or self._vm_name
        mem_key = CONSTRAINT_KEYS['mem']
        mem = params.get(mem_key)
        assert isinstance(mem, int)
        cpu = params.get(CONSTRAINT_KEYS['cpu'])

        min_mem = MIN_CONSTRAINTS[mem_key]
        dyn_mem_ratio = mem / min_mem

        try:
            self._vm_utils.update_vm(
                vm_name=name,
                memory_mb=mem,
                memory_per_numa_node=0,
                vcpus_num=cpu,
                vcpus_per_numa_node=0,
                limit_cpu_features=False,
                dynamic_mem_ratio=dyn_mem_ratio
            )
        except OSWinException:
            logger.exception(f'Hyper-V: reconfiguration of VM "{name}" failed')

        logger.info('Hyper-V: reconfiguration of VM "%s" finished', name)

    def update_work_dir(self, work_dir: Path) -> None:
        super().update_work_dir(work_dir)
        # Ensure that working directory is shared via SMB
        smbshare.create_share(self.DOCKER_USER, work_dir)

    @classmethod
    def _get_vswitch_name(cls) -> str:
        return cls._run_ps(cls.GET_VSWITCH_SCRIPT_PATH)

    @classmethod
    def _get_hostname_for_sharing(cls) -> str:
        """
        Get name of the host machine which could be used for sharing
        directories with Hyper-V VMs connected to Golem's virtual switch.
        """
        hostname = os.getenv('COMPUTERNAME')
        if not hostname:
            raise RuntimeError('COMPUTERNAME environment variable not set')
        return hostname

    @classmethod
    def _run_ps(cls, script, timeout=SCRIPT_TIMEOUT):
        """
        Runs the script and returns its output in UTF8
        """
        try:
            return subprocess\
                .run(
                    [
                        'powershell.exe',
                        '-ExecutionPolicy', 'RemoteSigned',
                        '-File', script,
                    ],
                    timeout=timeout,  # seconds
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )\
                .stdout\
                .decode('utf8')\
                .strip()
        except (CalledProcessError, TimeoutExpired) as exc:
            raise RuntimeError(exc.stderr.decode('utf8') if exc.stderr else '')

    @staticmethod
    def uses_volumes() -> bool:
        return True

    def create_volumes(self, binds: Iterable[DockerBind]) -> dict:
        hostname = self._get_hostname_for_sharing()
        return {
            self._create_volume(hostname, bind.source): {
                'bind': bind.target,
                'mode': bind.mode
            }
            for bind in binds
        }

    def _create_volume(self, hostname: str, shared_dir: Path) -> str:
        assert self._work_dir is not None
        try:
            relpath = shared_dir.relative_to(self._work_dir)
        except ValueError:
            raise ValueError(
                f'Cannot create docker volume: "{shared_dir}" is not a '
                f'subdirectory of docker work dir ("{self._work_dir}")')

        share_name = smbshare.get_share_name(self._work_dir)
        volume_name = f'{hostname}/{share_name}/{relpath.as_posix()}'

        # Client must be created here, do it in __init__() will not work since
        # environment variables are not set yet when __init__() is called
        client = local_client()
        client.create_volume(
            name=volume_name,
            driver=self.VOLUME_DRIVER,
            driver_opts={
                'username': self.DOCKER_USER,
                'password': self.DOCKER_PASSWORD
            }
        )

        return volume_name
