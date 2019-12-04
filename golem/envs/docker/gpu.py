from copy import copy
from logging import getLogger, Logger
from typing import Any, Dict, List, Optional

from dataclasses import dataclass, field
from golem_task_api.envs import DOCKER_GPU_ENV_ID

from golem.core.common import update_dict
from golem.envs import (
    EnvMetadata,
    EnvSupportStatus
)
from golem.envs.docker import DockerRuntimePayload
from golem.envs.docker.cpu import (
    DockerCPUEnvironment,
    DockerCPUConfig,
    DockerCPURuntime,
)
from golem.envs.docker.vendor import nvidia

logger = getLogger(__name__)


DOCKER_GPU_METADATA = EnvMetadata(
    id=DOCKER_GPU_ENV_ID,
    description='Docker environment using GPU'
)


@dataclass
class DockerGPUConfig(DockerCPUConfig):
    # GPU vendor identifier
    gpu_vendor: str = 'UNKNOWN'
    # GPU device list
    gpu_devices: List[str] = field(default_factory=list)
    # Enabled GPU device capabilities
    gpu_caps: List[str] = field(default_factory=list)
    # GPU device and driver constraints
    gpu_requirements: Dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        pass

    def container_config(self) -> Dict[str, Any]:
        raise NotImplementedError


@dataclass
class DockerNvidiaGPUConfig(DockerGPUConfig):

    gpu_vendor: str = field(
        default=nvidia.VENDOR)
    gpu_devices: List[str] = field(
        default_factory=lambda: copy(nvidia.DEFAULT_DEVICES))
    gpu_caps: List[str] = field(
        default_factory=lambda: copy(nvidia.DEFAULT_CAPABILITIES))
    gpu_requirements: Dict[str, str] = field(
        default_factory=lambda: copy(nvidia.DEFAULT_REQUIREMENTS))

    def validate(self) -> None:
        nvidia.validate_devices(self.gpu_devices)
        nvidia.validate_capabilities(self.gpu_caps)
        nvidia.validate_requirements(self.gpu_requirements)

    def container_config(self) -> Dict[str, Any]:
        environment = {
            # Golem
            'GPU_ENABLED': '1',
            'GPU_VENDOR': self.gpu_vendor,
            # nvidia-container-runtime
            'NVIDIA_VISIBLE_DEVICES': ','.join(self.gpu_devices),
            'NVIDIA_DRIVER_CAPABILITIES': ','.join(self.gpu_caps),
        }

        # pylint: disable=no-member
        for req, val in self.gpu_requirements.items():
            environment[f'NVIDIA_REQUIRE_{req.upper()}'] = val
        # pylint: enable=no-member

        return dict(
            runtime='nvidia',
            environment=environment,
        )


class DockerGPURuntime(DockerCPURuntime):

    pass


class DockerGPUEnvironment(DockerCPUEnvironment):

    BENCHMARK_IMAGE = 'golemfactory/gpu_benchmark:1.0'

    # Enforce DockerGPUConfig config class type (DockerCPUConfig in super)
    def __init__(  # pylint: disable=useless-super-delegation
            self,
            config: DockerGPUConfig,
            env_logger: Optional[Logger] = None,
    ) -> None:
        super().__init__(config, env_logger or logger)

    @classmethod
    def supported(cls) -> EnvSupportStatus:
        if not nvidia.is_supported():
            return EnvSupportStatus(False, "No supported GPU found")
        return super().supported()

    @classmethod
    def parse_config(cls, config_dict: Dict[str, Any]) -> DockerGPUConfig:
        if config_dict['gpu_vendor'] == nvidia.VENDOR:
            return DockerNvidiaGPUConfig(**config_dict)
        return DockerGPUConfig(**config_dict)

    @classmethod
    def _validate_config(cls, config: DockerCPUConfig) -> None:
        if not isinstance(config, DockerGPUConfig):
            raise ValueError(f"Invalid config class: '{config.__class__}'")

        super()._validate_config(config)
        config.validate()

    def _create_container_config(
            self,
            config: DockerCPUConfig,
            payload: DockerRuntimePayload,
    ) -> Dict[str, Any]:
        if not isinstance(config, DockerGPUConfig):
            raise ValueError(f"Invalid config class: '{config.__class__}'")

        container_config = super()._create_container_config(config, payload)
        update_dict(container_config, config.container_config())
        return container_config

    def _create_runtime(
            self,
            config: DockerCPUConfig,
            payload: DockerRuntimePayload,
    ) -> DockerCPURuntime:
        container_config = self._create_container_config(config, payload)
        return DockerGPURuntime(
            container_config,
            self._port_mapper,
            runtime_logger=self._logger)
