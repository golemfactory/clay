import logging
import os
import psutil
from pathlib import Path
import subprocess
from typing import Any, ClassVar, Dict, Iterable, List, Optional, Union

from os_win.constants import HOST_SHUTDOWN_ACTION_SAVE, \
    VM_SNAPSHOT_TYPE_DISABLED, HYPERV_VM_STATE_SUSPENDED, \
    HYPERV_VM_STATE_ENABLED, HOST_SHUTDOWN_ACTION_SHUTDOWN, \
    HYPERV_VM_STATE_DISABLED
from os_win.exceptions import OSWinException
from os_win.utils.compute.vmutils import VMUtils

from golem import hardware
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
        no_virt_mem='--hyperv-disable-dynamic-memory',
        virtual_switch='--hyperv-virtual-switch'
    )
    BOOT2DOCKER_URL = "https://github.com/golemfactory/boot2docker/releases/" \
                      "download/v18.06.1-ce%2Bdvn-v0.35/boot2docker.iso"
    DOCKER_USER = "golem-docker"
    DOCKER_PASSWORD = "golem-docker"
    VOLUME_SIZE = "5000"  # = 5GB; default was 20GB
    VOLUME_DRIVER = "cifs"
    SMB_PORT = "445"

    SCRIPTS_PATH = os.path.join(get_golem_path(), 'scripts', 'docker')
    GET_VSWITCH_SCRIPT_PATH = \
        os.path.join(SCRIPTS_PATH, 'get-default-vswitch.ps1')
    START_VM_SCRIPT_PATH = \
        os.path.join(SCRIPTS_PATH, 'start-hyperv-docker-vm.ps1')
    SCRIPT_TIMEOUT = 5  # seconds
    START_VM_TIMEOUT = 60  # seconds

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._vm_utils = VMUtils()

    def setup(self) -> None:
        super().setup()
        self._check_smb_port()

    def _check_smb_port(self) -> None:
        ok_str = 'Port check OK'
        hostname = self._get_hostname_for_sharing()
        output = self.command('execute', args=[
            self._vm_name,
            f'if nc -z -w 1 {hostname} {self.SMB_PORT} ; then echo {ok_str} ; '
            f'else echo Error ; fi'
        ])
        # We use splitlines() because output may contain multiple lines with
        # debug information
        if output is None or ok_str not in output.splitlines():
            logger.error(
                f'Port {self.SMB_PORT} unreachable. '
                f'Please check firewall settings.')

    def save_vm(self, vm_name: Optional[str] = None) -> None:
        vm_name = vm_name or self._vm_name
        logger.info('Hyper-V: Saving state of VM %s ...', vm_name)
        try:
            self._vm_utils.set_vm_state(vm_name, HYPERV_VM_STATE_SUSPENDED)
        except OSWinException:
            logger.exception(
                'Hyper-V: Saving VM %s state failed. Stopping VM ...', vm_name)
            self.stop_vm(vm_name)

    def restore_vm(self, vm_name: Optional[str] = None) -> None:
        vm_name = vm_name or self._vm_name
        vm_state = self._vm_utils.get_vm_state(vm_name)

        if vm_state == HYPERV_VM_STATE_SUSPENDED:

            if self._check_memory():
                logger.info('Hyper-V: Restoring VM %s ...', vm_name)
                try:
                    self._vm_utils.set_vm_state(
                        vm_name,
                        HYPERV_VM_STATE_ENABLED
                    )
                    return
                except OSWinException:
                    logger.exception(f'Hyper-V: Failed to restore VM {vm_name}')

            # If check_memory returned false or resuming raised an exception
            # try to remove the saved state and restart it
            logger.info('Hyper-V: VM %s cannot be restored. '
                        'Removing the saved state ...', vm_name)
            self._vm_utils.set_vm_state(vm_name, HYPERV_VM_STATE_DISABLED)

        logger.info(
            'Hyper-V: VM %s cannot be restored. Booting ...', vm_name)
        self.start_vm(vm_name)

    def start_vm(self, name: Optional[str] = None) -> None:
        name = name or self._vm_name
        constr = self.constraints()

        if not self._check_memory(constr):
            logger.warning('Not enough memory to start the VM, lowering memory')
            mem_key = CONSTRAINT_KEYS['mem']
            max_memory = self._memory_cap(constr[mem_key])
            constr[mem_key] = hardware.cap_memory(constr[mem_key], max_memory,
                                                  unit=hardware.MemSize.mebi)
            logger.debug('Memory capped by "free - 10%%": %r', constr[mem_key])

        # Always constrain to set the appropriate shutdown action
        self.constrain(name, **constr)

        try:
            # The windows VM fails to start when too much memory is assigned
            logger.info("Hyper-V: Starting VM %s ...", name)
            self._run_ps(
                script=self.START_VM_SCRIPT_PATH,
                args=[
                    '-VMName', name,
                    '-IPTimeoutSeconds', str(self.START_VM_TIMEOUT)
                ],
                timeout=self.START_VM_TIMEOUT
            )
            logger.info("Hyper-V: VM %s started successfully", name)
        except subprocess.CalledProcessError:
            logger.error(
                "Hyper-V: VM failed to start, this can be caused "
                "by insufficient RAM or HD free on the host machine")
            raise

    @classmethod
    def is_available(cls) -> bool:
        command = "@(Get-Module -ListAvailable hyper-v).Name | Get-Unique"
        try:
            output = cls._run_ps(command=command)
            return output == "Hyper-V"
        except (RuntimeError, OSError) as e:
            logger.warning(f"Error checking Hyper-V availability: {e}")
            return False

    # pylint: disable=arguments-differ
    def _parse_create_params(
            self,
            cpu: Optional[int] = None,
            mem: Optional[int] = None,
            **params: Any) -> List[str]:

        args = super()._parse_create_params(**params)
        virtual_switch = self._get_vswitch_name()
        args += [
            self.OPTIONS['boot2docker_url'], self.BOOT2DOCKER_URL,
            self.OPTIONS['virtual_switch'], virtual_switch,
            self.OPTIONS['disk'], self.VOLUME_SIZE,
            self.OPTIONS['no_virt_mem'],
        ]

        if cpu is not None:
            args += [self.OPTIONS['cpu'], str(cpu)]
        if mem is not None:
            cap_mem = self._memory_cap(mem)
            if cap_mem != mem:
                logger.warning('Not enough memory to create the VM. '
                               'Lowering memory to %d MiB', cap_mem)

            if self._check_system_drive_space(cap_mem):
                args += [self.OPTIONS['mem'], str(cap_mem)]
            else:
                logger.warning("Not enough disk space. "
                               "Creating VM with min memory")
                mem_key = CONSTRAINT_KEYS['mem']
                args += [self.OPTIONS['mem'], str(MIN_CONSTRAINTS[mem_key])]

        return args

    def _failed_to_create(self, vm_name: Optional[str] = None):
        name = vm_name or self._vm_name
        logger.error(
            f'{ self.DRIVER_NAME}: VM failed to create, this can be '
            'caused by insufficient RAM or HD free on the host machine')
        try:
            self.command('rm', name, args=['-f'])
        except subprocess.CalledProcessError:
            logger.error(
                f'{ self.DRIVER_NAME}: Failed to clean up a (possible) '
                'corrupt machine, please run: '
                f'`docker-machine rm -y -f {name}`')

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

        if self._check_system_drive_space(mem):
            shutdown_action = HOST_SHUTDOWN_ACTION_SAVE
        else:
            logger.warning("Not enough space on system drive. VM state cannot"
                           "be saved on system shutdown")
            shutdown_action = HOST_SHUTDOWN_ACTION_SHUTDOWN

        try:
            self._vm_utils.update_vm(
                vm_name=name,
                memory_mb=mem,
                memory_per_numa_node=0,
                vcpus_num=cpu,
                vcpus_per_numa_node=0,
                limit_cpu_features=False,
                dynamic_mem_ratio=1,
                host_shutdown_action=shutdown_action,
                snapshot_type=VM_SNAPSHOT_TYPE_DISABLED,
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
        return cls._run_ps(script=cls.GET_VSWITCH_SCRIPT_PATH)

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
    def _run_ps(
            cls,
            script: Optional[str] = None,
            command: Optional[str] = None,
            args: Optional[List[str]] = None,
            timeout: int = SCRIPT_TIMEOUT
    ) -> str:
        """
        Run a powershell script or command and return its output in UTF8
        """
        cmd = [
            'powershell.exe', '-NoProfile'
        ]
        if script and not command:
            cmd += [
                '-ExecutionPolicy', 'RemoteSigned',
                '-File', script
            ]
        elif command and not script:
            cmd += [
                '-Command', command
            ]
        else:
            raise ValueError("Exactly one of (script, command) is required")

        if args:
            cmd += args

        try:
            return subprocess\
                .run(
                    cmd,
                    timeout=timeout,  # seconds
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )\
                .stdout\
                .decode('utf8')\
                .strip()
        except (subprocess.CalledProcessError, \
                subprocess.TimeoutExpired) as exc:
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

    def _memory_cap(self, memory: int) -> int:
        return min(memory, self._get_max_memory())

    def _check_memory(self, constr: Optional[dict] = None) -> bool:
        """
        Checks if there is enough memory on the system to start the VM
        If not try to free memory and check again
        """
        if self.vm_running():
            return True

        constr = constr or self.constraints()
        mem = constr[CONSTRAINT_KEYS['mem']]

        if mem > self._get_max_memory():
            logger.info("Attempting to free memory (empty working sets of "
                        "running processes)")
            try:
                from golem.os import windows_ews
                windows_ews()
            except (ImportError, OSError):
                logger.exception('Failed to free memory')

        return mem <= self._get_max_memory(constr)

    @staticmethod
    def _check_system_drive_space(memory: int) -> bool:
        """
        Check if there is enough space on the system drive to dump virtual
        machine memory when the host machine is shutting down
        :param memory: VM assigned memory in MiB
        """
        drive = os.getenv('SystemDrive')
        free_space = psutil.disk_usage(drive).free // 1024 // 1024
        return memory < free_space

    def _get_max_memory(self, constr: Optional[dict] = None) -> int:
        max_mem_in_mb = hardware.memory_available() // 1024

        if self.vm_running():
            constr = constr or self.constraints()
            max_mem_in_mb += constr[CONSTRAINT_KEYS['mem']]

        return hardware.pad_memory(int(0.9 * max_mem_in_mb))

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
