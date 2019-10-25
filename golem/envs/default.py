from pathlib import Path

from golem_task_api.envs import DOCKER_CPU_ENV_ID, DOCKER_GPU_ENV_ID

from golem.envs.auto_setup import auto_setup
from golem.envs.docker.cpu import DockerCPUConfig, DOCKER_CPU_METADATA
from golem.envs.docker.gpu import DOCKER_GPU_METADATA
from golem.envs.docker.non_hypervised import (
    NonHypervisedDockerCPUEnvironment,
    NonHypervisedDockerGPUEnvironment,
)
from golem.envs.docker.whitelist import Whitelist
from golem.task.envmanager import EnvironmentManager
from golem.task.task_api.docker import DockerTaskApiPayloadBuilder

DOCKER_REPOSITORY = "golemfactory"


def _register_docker_cpu_env(
        work_dir: str,
        env_manager: EnvironmentManager
) -> None:
    docker_cpu_config = DockerCPUConfig(work_dirs=[Path(work_dir)])
    docker_cpu_env = auto_setup(
        NonHypervisedDockerCPUEnvironment(docker_cpu_config))

    env_manager.register_env(
        docker_cpu_env,
        DOCKER_CPU_METADATA,
        DockerTaskApiPayloadBuilder,
    )
    env_manager.set_enabled(DOCKER_CPU_ENV_ID, True)


def _register_docker_gpu_env(
        work_dir: str,
        env_manager: EnvironmentManager
) -> None:
    docker_config_dict = dict(work_dirs=[work_dir])
    docker_gpu_env = auto_setup(
        NonHypervisedDockerGPUEnvironment.default(docker_config_dict))

    env_manager.register_env(
        docker_gpu_env,
        DOCKER_GPU_METADATA,
        DockerTaskApiPayloadBuilder)
    env_manager.set_enabled(DOCKER_GPU_ENV_ID, True)


def register_built_in_repositories():

    if not Whitelist.is_whitelisted(DOCKER_REPOSITORY):
        Whitelist.add(DOCKER_REPOSITORY)


def register_environments(
        work_dir: str,
        env_manager: EnvironmentManager
) -> None:

    if NonHypervisedDockerCPUEnvironment.supported().supported:
        _register_docker_cpu_env(work_dir, env_manager)

    if NonHypervisedDockerGPUEnvironment.supported().supported:
        _register_docker_gpu_env(work_dir, env_manager)
