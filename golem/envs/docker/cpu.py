import logging
from pathlib import Path
from subprocess import SubprocessError
from typing import Optional, Callable, Any, Dict, List, Type, ClassVar, \
    NamedTuple

from twisted.internet.defer import Deferred
from twisted.internet.threads import deferToThread

from golem.core.common import is_linux, is_windows, is_osx
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

    @classmethod
    def from_dict(cls, dict_: Dict[str, Any]) -> 'DockerCPUConfig':
        work_dir = Path(dict_.pop('work_dir'))
        return DockerCPUConfig(work_dir=work_dir, **dict_)


class DockerCPURuntime(Runtime):

    def __init__(self, payload: DockerPayload, config: DockerCPUConfig) -> None:
        pass

    def start(self) -> Deferred:
        raise NotImplementedError

    def stop(self) -> Deferred:
        raise NotImplementedError

    def status(self) -> RuntimeStatus:
        raise NotImplementedError

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

    MIN_MEMORY_MB = 1024
    MIN_CPU_COUNT = 1

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
            logger.info('Checking docker version failed.')
            return False
        if version_string is None:
            logger.info('Docker version returned no output.')
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

    def prepare_prerequisites(self, prerequisites: Prerequisites) -> Deferred:
        assert isinstance(prerequisites, DockerPrerequisites)
        if self._status != EnvStatus.ENABLED:
            raise ValueError(f"Cannot prepare prerequisites because environment"
                             f"is in invalid state: '{self._status}'")
        logger.info("Preparing prerequisites...")

        def _prepare():
            args = [f"{prerequisites.image}:{prerequisites.tag}"]
            try:
                DockerCommandHandler.run("pull", args=args)
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
        logger.info("Creating runtime...")
        return DockerCPURuntime(payload, config)

