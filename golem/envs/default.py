import logging
from pathlib import Path

from golem_task_api.envs import DOCKER_CPU_ENV_ID, DOCKER_GPU_ENV_ID

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
logger = logging.getLogger(__name__)


def _register_docker_cpu_env(
        work_dir: str,
        env_manager: EnvironmentManager,
        dev_mode: bool,
) -> None:
    docker_cpu_config = DockerCPUConfig(work_dirs=[Path(work_dir)])
    docker_cpu_env = NonHypervisedDockerCPUEnvironment(
        docker_cpu_config,
        dev_mode,
    )

    env_manager.register_env(
        docker_cpu_env,
        DOCKER_CPU_METADATA,
        DockerTaskApiPayloadBuilder,
    )
    env_manager.set_enabled(DOCKER_CPU_ENV_ID, True)


def _register_docker_gpu_env(
        work_dir: str,
        env_manager: EnvironmentManager,
        dev_mode: bool,
) -> None:
    docker_config_dict = dict(work_dirs=[work_dir])
    docker_gpu_env = NonHypervisedDockerGPUEnvironment.default(
        docker_config_dict,
        dev_mode,
    )

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
        env_manager: EnvironmentManager,
        dev_mode: bool,
) -> None:
    ENVS = [
        (
            DOCKER_CPU_ENV_ID,
            NonHypervisedDockerCPUEnvironment,
            _register_docker_cpu_env
        ),
        (
            DOCKER_GPU_ENV_ID,
            NonHypervisedDockerGPUEnvironment,
            _register_docker_gpu_env
        ),
    ]
    from golem.config.active import TASK_API_ENVS
    for (env_id, env_cls, _register) in ENVS:
        if env_id not in TASK_API_ENVS:
            logger.debug('Environment disabled. env_id=%r', env_id)
            continue
        if not env_cls.supported().supported:
            logger.info('Environment not supported. env_id=%r', env_id)
            continue
        logger.info('Registering environment. env_id=%r', env_id)
        _register(work_dir, env_manager, dev_mode)
