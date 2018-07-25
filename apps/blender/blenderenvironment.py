from os import path
from typing import Dict

from apps.core import nvgpu
from apps.core.nvgpu import get_devices
from golem.core.common import get_golem_path, posix_path
from golem.docker.environment import DockerEnvironment
from golem.docker.image import DockerImage
from golem.environments.environment import SupportStatus


class BlenderEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/blender"
    DOCKER_TAG = "1.4"
    ENV_ID = "BLENDER"
    APP_DIR = path.join(get_golem_path(), 'apps', 'blender')
    SCRIPT_NAME = "docker_blendertask.py"
    SHORT_DESCRIPTION = "Blender (www.blender.org)"


class BlenderNVGPUEnvironment(BlenderEnvironment):
    # pylint: disable=too-few-public-methods

    DOCKER_IMAGE = "golemfactory/blender_nvgpu"
    DOCKER_TAG = "1.0"
    ENV_ID = "BLENDER_NVGPU"
    SHORT_DESCRIPTION = "Blender + NVIDIA GPU (www.blender.org)"

    def __init__(self) -> None:
        super().__init__(additional_images=[DockerImage(
            repository=BlenderEnvironment.DOCKER_IMAGE,
            tag=BlenderEnvironment.DOCKER_TAG,
        )])

    def check_support(self) -> SupportStatus:
        if not nvgpu.is_supported():
            return SupportStatus.err('NVIDIA GPU environment is not supported')
        return super().check_support()

    def get_container_config(self) -> Dict:
        devices = [f'/dev/nvidia{d}:/dev/nvidia{d}' for d in get_devices()]
        return dict(
            runtime='nvidia',
            volumes=[
                '/tmp/.X11-unix',
            ],
            binds={
                posix_path('/tmp/.X11-unix'): {
                    "bind": '/tmp/.X11-unix',
                    "mode": "rw"
                }
            },
            devices=[
                '/dev/nvidiactl:/dev/nvidiactl',
                '/dev/nvidia-uvm:/dev/nvidia-uvm',
            ] + devices,
            environment={},
        )
