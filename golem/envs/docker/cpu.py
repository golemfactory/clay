import logging
from functools import wraps
from pathlib import Path
from subprocess import SubprocessError
from threading import Lock, Thread
from time import sleep
from typing import Optional, Callable, Any, Dict, List, Type, ClassVar, \
    NamedTuple, Union, Sequence, Tuple

from docker.errors import APIError
from twisted.internet.defer import Deferred
from twisted.internet.threads import deferToThread

from golem import hardware
from golem.core.common import is_linux, is_windows, is_osx
from golem.docker.client import local_client
from golem.docker.commands.docker import DockerCommandHandler
from golem.docker.config import CONSTRAINT_KEYS
from golem.docker.hypervisor import Hypervisor
from golem.docker.hypervisor.docker_for_mac import DockerForMac
from golem.docker.hypervisor.dummy import DummyHypervisor
from golem.docker.hypervisor.hyperv import HyperVHypervisor
from golem.docker.hypervisor.virtualbox import VirtualBoxHypervisor
from golem.docker.hypervisor.xhyve import XhyveHypervisor
from golem.envs import Environment, EnvSupportStatus, Payload, EnvConfig, \
    Runtime, EnvEventId, EnvEvent, EnvMetadata, EnvStatus, RuntimeEventId, \
    RuntimeEvent, CounterId, CounterUsage, RuntimeStatus, EnvId, Prerequisites
from golem.envs.docker import DockerPayload, DockerPrerequisites

logger = logging.getLogger(__name__)

# Keys used by hypervisors for memory and CPU constraints
mem = CONSTRAINT_KEYS['mem']
cpu = CONSTRAINT_KEYS['cpu']


class DockerCPUConfigData(NamedTuple):
    work_dir: Path
    memory_mb: int = 1024
    cpu_count: int = 1


class DockerCPUConfig(DockerCPUConfigData, EnvConfig):
    """ This exists because NamedTuple must be single superclass """

    def to_dict(self) -> Dict[str, Any]:
        dict_ = self._asdict()
        dict_['work_dir'] = str(dict_['work_dir'])
        return dict_

    @staticmethod
    def from_dict(dict_: Dict[str, Any]) -> 'DockerCPUConfig':
        work_dir = Path(dict_.pop('work_dir'))
        return DockerCPUConfig(work_dir=work_dir, **dict_)


class DockerCPURuntime(Runtime):

    CONTAINER_RUNNING: ClassVar[List[str]] = ["running"]
    CONTAINER_STOPPED: ClassVar[List[str]] = ["exited", "dead"]

    STATUS_UPDATE_INTERVAL = 1.0  # seconds

    def __init__(self, payload: DockerPayload, host_config: Dict[str, Any]) \
            -> None:
        image = f"{payload.image}:{payload.tag}"
        volumes = [bind.target for bind in payload.binds]
        if payload.command is not None:
            command: Optional[List[str]] = [payload.command] + payload.args
        else:
            command = None
        client = local_client()

        self._status = RuntimeStatus.CREATED
        self._status_lock = Lock()
        self._status_update_thread: Optional[Thread] = None
        self._container_id: Optional[str] = None
        self._container_config = client.create_container_config(
            image=image,
            volumes=volumes,
            command=command,
            user=payload.user,
            environment=payload.env,
            working_dir=payload.work_dir,
            host_config=host_config
        )

    def _change_status(
            self,
            from_status: Union[RuntimeStatus, Sequence[RuntimeStatus]],
            to_status: RuntimeStatus) -> None:
        """ Assert that current Runtime status is the given one and change to
            another one. Using lock to ensure atomicity. """

        if isinstance(from_status, RuntimeStatus):
            from_status = [from_status]

        with self._status_lock:
            if self._status not in from_status:
                exp_status = "or ".join(map(str, from_status))
                raise ValueError(
                    f"Invalid status: {self._status}. Expected: {exp_status}")
            self._status = to_status

    def _wrap_status_change(
            self,
            success_status: RuntimeStatus,
            error_status: RuntimeStatus = RuntimeStatus.FAILURE,
            success_msg: Optional[str] = None,
            error_msg: Optional[str] = None
    ) -> Callable[[Callable[[], None]], Callable[[], None]]:
        """ Wrap function. If it fails log error_msg, set status to
            error_status, and re-raise the exception. Otherwise log success_msg
            and set status to success_status. Setting status uses lock. """

        def wrapper(func: Callable[[], None]):

            @wraps(func)
            def wrapped():
                try:
                    func()
                except Exception:
                    if error_msg:
                        logger.exception(error_msg)
                    with self._status_lock:
                        self._status = error_status
                    raise
                else:
                    if success_msg:
                        logger.info(success_msg)
                    with self._status_lock:
                        self._status = success_status

            return wrapped

        return wrapper

    def _inspect_container(self) -> Tuple[str, int]:
        """ Inspect Docker container associated with this runtime. Returns
            (status, exit_code) tuple. """
        assert self._container_id is not None
        client = local_client()
        inspection = client.inspect_container(self._container_id)
        state = inspection["State"]
        return state["Status"], state["ExitCode"]

    def _update_status(self) -> None:
        """ Periodically check status of the container and update the Runtime's
            status accordingly. Assumes the container has been started and not
            removed. Uses lock for status read & write. """
        while True:
            sleep(self.STATUS_UPDATE_INTERVAL)
            logger.debug("Updating runtime status...")

            with self._status_lock:
                if self._status != RuntimeStatus.RUNNING:
                    logger.info("Runtime is no longer running. "
                                "Stopping status update thread.")
                    return

                try:
                    container_status, exit_code = self._inspect_container()
                except (APIError, KeyError):
                    logger.exception("Error inspecting container.")
                    self._status = RuntimeStatus.FAILURE
                    return

                if container_status in self.CONTAINER_RUNNING:
                    logger.debug("Container still running, no status update.")
                    continue

                elif container_status in self.CONTAINER_STOPPED:
                    logger.info("Container stopped.")
                    self._status = RuntimeStatus.STOPPED if exit_code == 0 \
                        else RuntimeStatus.FAILURE
                    return

                else:
                    logger.error(
                        f"Unexpected container status: '{container_status}'")
                    self._status = RuntimeStatus.FAILURE
                    return

    def prepare(self) -> Deferred:
        self._change_status(
            from_status=RuntimeStatus.CREATED,
            to_status=RuntimeStatus.PREPARING)
        logger.info("Preparing runtime...")

        @self._wrap_status_change(
            success_status=RuntimeStatus.PREPARED,
            success_msg="Container successfully created.",
            error_msg="Creating container failed.")
        def _prepare():
            client = local_client()
            result = client.create_container_from_config(self._container_config)

            container_id = result.get("Id")
            assert isinstance(container_id, str), "Invalid container ID"
            self._container_id = container_id

            for warning in result.get("Warnings", []):
                logger.warning("Container creation warning: %s", warning)

        return deferToThread(_prepare)

    def cleanup(self) -> Deferred:
        self._change_status(
            from_status=[RuntimeStatus.FAILURE, RuntimeStatus.STOPPED],
            to_status=RuntimeStatus.CLEANING_UP)
        logger.info("Cleaning up runtime...")

        @self._wrap_status_change(
            success_status=RuntimeStatus.TORN_DOWN,
            success_msg=f"Container '{self._container_id}' removed.",
            error_msg=f"Failed to remove container '{self._container_id}'")
        def _cleanup():
            client = local_client()
            client.remove_container(self._container_id)

        return deferToThread(_cleanup)

    def start(self) -> Deferred:
        self._change_status(
            from_status=RuntimeStatus.PREPARED,
            to_status=RuntimeStatus.STARTING)
        logger.info("Starting container '%s'...", self._container_id)

        @self._wrap_status_change(
            success_status=RuntimeStatus.STARTED,
            success_msg=f"Container '{self._container_id}' started.",
            error_msg=f"Starting container '{self._container_id}' failed.")
        def _start():
            client = local_client()
            client.start(self._container_id)

        def _spawn_status_update_thread():
            logger.debug("Spawning status update thread...")
            self._status_update_thread = Thread(target=self._update_status)
            self._status_update_thread.start()
            logger.debug("Status update thread spawned.")

        deferred_start = deferToThread(_start)
        deferred_start.addCallback(_spawn_status_update_thread)
        return deferred_start

    def stop(self) -> Deferred:
        with self._status_lock:
            if self._status != RuntimeStatus.RUNNING:
                raise ValueError(f"Invalid status: {self._status}")
        logger.info("Stopping container '%s'...", self._container_id)

        @self._wrap_status_change(
            success_status=RuntimeStatus.STOPPED,
            success_msg=f"Container '{self._container_id}' stopped.",
            error_msg=f"Stopping container '{self._container_id}' failed.")
        def _stop():
            client = local_client()
            client.stop(self._container_id)

        def _join_status_update_thread():
            logger.debug("Joining status update thread...")
            self._status_update_thread.join(self.STATUS_UPDATE_INTERVAL * 2)
            if self._status_update_thread.is_alive():
                logger.warning("Failed to join status update thread.")
            else:
                logger.debug("Status update thread joined.")

        deferred_stop = deferToThread(_stop)
        deferred_stop.addCallback(_join_status_update_thread)
        return deferred_stop

    def status(self) -> RuntimeStatus:
        with self._status_lock:
            return self._status

    def usage_counters(self) -> Dict[CounterId, CounterUsage]:
        raise NotImplementedError

    def listen(self, event_id: RuntimeEventId,
               callback: Callable[[RuntimeEvent], Any]) -> None:
        raise NotImplementedError

    def call(self, alias: str, *args, **kwargs) -> Deferred:
        raise NotImplementedError


class DockerCPUEnvironment(Environment):

    ENV_ID: ClassVar[EnvId] = 'docker_cpu'
    ENV_DESCRIPTION: ClassVar[str] = 'Docker environment using CPU'

    SUPPORTED_DOCKER_VERSIONS: ClassVar[List[str]] = ['18.06.1-ce']

    MIN_MEMORY_MB: ClassVar[int] = 1024
    MIN_CPU_COUNT: ClassVar[int] = 1

    NETWORK_MODE: ClassVar[str] = 'none'
    DNS_SERVERS: ClassVar[List[str]] = []
    DNS_SEARCH_DOMAINS: ClassVar[List[str]] = []
    DROPPED_KERNEL_CAPABILITIES: ClassVar[List[str]] = [
        'audit_control',
        'audit_write',
        'mac_admin',
        'mac_override',
        'mknod',
        'net_admin',
        'net_bind_service',
        'net_raw',
        'setfcap',
        'setpcap',
        'sys_admin',
        'sys_boot',
        'sys_chroot',
        'sys_module',
        'sys_nice',
        'sys_pacct',
        'sys_resource',
        'sys_time',
        'sys_tty_config'
    ]

    @classmethod
    def supported(cls) -> EnvSupportStatus:
        logger.info('Checking environment support status...')
        if not DockerCommandHandler.docker_available():
            return EnvSupportStatus(False, "Docker executable not found")
        if not cls._check_docker_version():
            return EnvSupportStatus(False, "Wrong docker version")
        if cls._get_hypervisor_class() is None:
            return EnvSupportStatus(False, "No supported hypervisor found")
        logger.info('Environment supported.')
        return EnvSupportStatus(True)

    @classmethod
    def _check_docker_version(cls) -> bool:
        logger.info('Checking docker version...')
        try:
            version_string = DockerCommandHandler.run("version")
        except SubprocessError:
            logger.exception('Checking docker version failed.')
            return False
        if version_string is None:
            logger.error('Docker version returned no output.')
            return False
        version = version_string.lstrip("Docker version ").split(",")[0]
        logger.info('Found docker version: %s', version)
        return version in cls.SUPPORTED_DOCKER_VERSIONS

    @classmethod
    def _get_hypervisor_class(cls) -> Optional[Type[Hypervisor]]:
        if is_linux():
            return DummyHypervisor
        if is_windows():
            if HyperVHypervisor.is_available():
                return HyperVHypervisor
            if VirtualBoxHypervisor.is_available():
                return VirtualBoxHypervisor
        if is_osx():
            if DockerForMac.is_available():
                return DockerForMac
            if XhyveHypervisor.is_available():
                return XhyveHypervisor
        return None

    def __init__(self, config: DockerCPUConfig) -> None:
        self._status = EnvStatus.DISABLED
        self._validate_config(config)
        self._config = config

        hypervisor_cls = self._get_hypervisor_class()
        if hypervisor_cls is None:
            raise EnvironmentError("No supported hypervisor found")
        self._hypervisor = hypervisor_cls.instance(self._get_hypervisor_config)

    def _get_hypervisor_config(self) -> Dict[str, int]:
        return {
            mem: self._config.memory_mb,
            cpu: self._config.cpu_count
        }

    def status(self) -> EnvStatus:
        return self._status

    def prepare(self) -> Deferred:
        if self._status != EnvStatus.DISABLED:
            raise ValueError(f"Cannot prepare because environment is in "
                             f"invalid state: '{self._status}'")
        self._status = EnvStatus.PREPARING
        logger.info("Preparing environment...")

        def _prepare():
            try:
                self._hypervisor.setup()
            except Exception:
                logger.exception("Preparing environment failed.")
                self._status = EnvStatus.DISABLED
                raise
            else:
                logger.info("Environment successfully enabled.")
                self._status = EnvStatus.ENABLED

        return deferToThread(_prepare)

    def cleanup(self) -> Deferred:
        if self._status != EnvStatus.ENABLED:
            raise ValueError(f"Cannot clean up because environment is in "
                             f"invalid state: '{self._status}'")
        self._status = EnvStatus.CLEANING_UP
        logger.info("Cleaning up environment...")

        def _clean_up():
            try:
                self._hypervisor.quit()
            except Exception:
                logger.exception("Cleaning up environment failed.")
                self._status = EnvStatus.ENABLED
                raise
            else:
                logger.info("Environment successfully disabled.")
                self._status = EnvStatus.DISABLED

        return deferToThread(_clean_up)

    @classmethod
    def metadata(cls) -> EnvMetadata:
        return EnvMetadata(
            id=cls.ENV_ID,
            description=cls.ENV_DESCRIPTION,
            supported_counters=[],  # TODO: Specify usage counters
            custom_metadata={}
        )

    @classmethod
    def parse_prerequisites(cls, prerequisites_dict: Dict[str, Any]) \
            -> DockerPrerequisites:
        return DockerPrerequisites(**prerequisites_dict)

    def install_prerequisites(self, prerequisites: Prerequisites) -> Deferred:
        assert isinstance(prerequisites, DockerPrerequisites)
        if self._status != EnvStatus.ENABLED:
            raise ValueError(f"Cannot prepare prerequisites because environment"
                             f"is in invalid state: '{self._status}'")
        logger.info("Preparing prerequisites...")

        def _prepare():
            try:
                client = local_client()
                client.pull(
                    prerequisites.image,
                    tag=prerequisites.tag
                )
            except Exception:
                logger.exception("Preparing prerequisites failed.")
                raise
            else:
                logger.info("Prerequisites prepared.")

        return deferToThread(_prepare)

    @classmethod
    def parse_config(cls, config_dict: Dict[str, Any]) -> DockerCPUConfig:
        return DockerCPUConfig(**config_dict)

    def config(self) -> DockerCPUConfig:
        return DockerCPUConfig(*self._config)

    def update_config(self, config: EnvConfig) -> None:
        assert isinstance(config, DockerCPUConfig)
        if self._status != EnvStatus.DISABLED:
            raise ValueError(
                "Config can be updated only when the environment is disabled")
        logger.info("Updating environment configuration...")

        self._validate_config(config)
        if config.work_dir != self._config.work_dir:
            self._hypervisor.update_work_dir(config.work_dir)
        self._constrain_hypervisor(config)
        self._config = DockerCPUConfig(*config)
        logger.info("Configuration updated.")

    @classmethod
    def _validate_config(cls, config: DockerCPUConfig) -> None:
        logger.info("Validating configuration...")
        if not config.work_dir.is_dir():
            raise ValueError(f"Invalid working directory: '{config.work_dir}'")
        if config.memory_mb < cls.MIN_MEMORY_MB:
            raise ValueError(f"Not enough memory: {config.memory_mb} MB")
        if config.cpu_count < cls.MIN_CPU_COUNT:
            raise ValueError(f"Not enough CPUs: {config.cpu_count}")
        logger.info("Configuration positively validated.")

    def _constrain_hypervisor(self, config: DockerCPUConfig) -> None:
        current = self._hypervisor.constraints()
        target = {
            mem: config.memory_mb,
            cpu: config.cpu_count
        }
        if target != current:
            logger.info("Hypervisor configuration differs. "
                        "Reconfiguring hypervisor...")
            try:
                with self._hypervisor.reconfig_ctx():
                    self._hypervisor.constrain(**target)
            except Exception:
                logger.exception("Reconfiguring hypervisor failed.")
                raise
            else:
                logger.info("Hypervisor successfully reconfigured.")
        else:
            logger.info("No need to reconfigure hypervisor.")

    def listen(self, event_id: EnvEventId,
               callback: Callable[[EnvEvent], Any]) -> None:
        pass  # TODO: Specify environment events

    @classmethod
    def parse_payload(cls, payload_dict: Dict[str, Any]) -> DockerPayload:
        return DockerPayload.from_dict(payload_dict)

    def runtime(self, payload: Payload, config: Optional[EnvConfig] = None) \
            -> DockerCPURuntime:
        assert isinstance(payload, DockerPayload)
        if config is not None:
            assert isinstance(config, DockerCPUConfig)
        else:
            config = self.config()

        host_config = self._create_host_config(config, payload)
        return DockerCPURuntime(payload, host_config)

    def _create_host_config(
            self, config: DockerCPUConfig, payload: DockerPayload) \
            -> Dict[str, Any]:

        cpus = hardware.cpus()[:config.cpu_count]
        cpuset_cpus = ','.join(map(str, cpus))
        mem_limit = f'{config.memory_mb}m'  # 'm' is for megabytes
        binds = self._hypervisor.create_volumes(payload.binds)

        client = local_client()
        return client.create_host_config(
            cpuset_cpus=cpuset_cpus,
            mem_limit=mem_limit,
            binds=binds,
            privileged=False,
            network_mode=self.NETWORK_MODE,
            dns=self.DNS_SERVERS,
            dns_search=self.DNS_SEARCH_DOMAINS,
            cap_drop=self.DROPPED_KERNEL_CAPABILITIES
        )
