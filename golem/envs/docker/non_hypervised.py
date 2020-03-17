from typing import Any, Dict

from golem.core.common import is_windows
from golem.docker.hypervisor.dummy import DummyHypervisor, DummyHyperVHypervisor
from golem.envs.docker.cpu import DockerCPUEnvironment
from golem.envs.docker.gpu import DockerGPUEnvironment, DockerGPUConfig


class NonHypervisedDockerCPUEnvironment(DockerCPUEnvironment):
    """ This is a temporary class that never uses a hypervisor. It just assumes
        that Docker VM is properly configured if needed. The purpose of this
        class is to use Docker CPU Environment alongside with DockerManager. """

    # TODO: Remove when DockerManager is removed

    @classmethod
    def _get_hypervisor_class(cls):
        if is_windows():
            return DummyHyperVHypervisor
        return DummyHypervisor


class NonHypervisedDockerGPUEnvironment(DockerGPUEnvironment):
    """ This is a temporary class that never uses a hypervisor. It just assumes
        that Docker VM is properly configured if needed. The purpose of this
        class is to use Docker GPU Environment alongside with DockerManager. """

    # TODO: Remove when DockerManager is removed

    @classmethod
    def _get_hypervisor_class(cls):
        return DummyHypervisor

    @classmethod
    def default(
            cls,
            config_dict: Dict[str, Any],
            dev_mode: bool,
    ) -> 'NonHypervisedDockerGPUEnvironment':
        from golem.envs.docker.vendor import nvidia
        config_dict = dict(config_dict)
        config_dict['gpu_vendor'] = nvidia.VENDOR
        docker_config = DockerGPUConfig.from_dict(config_dict)
        # Make linters know that docker_config is an instance of DockerGPUConfig
        assert isinstance(docker_config, DockerGPUConfig)
        return cls(docker_config, dev_mode)
