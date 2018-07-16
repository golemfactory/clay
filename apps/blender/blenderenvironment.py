from os import path
from typing import List, Dict, Optional

from apps.core import nvgpu
from golem.core.common import get_golem_path, posix_path
from golem.docker.environment import DockerEnvironment
from golem.docker.image import DockerImage


class BlenderEnvironmentChooser:

    def __new__(cls, *args, **kwargs):
        if nvgpu.is_supported():
            instance = BlenderNVGPUEnvironment.__new__(BlenderNVGPUEnvironment)
        else:
            instance = BlenderEnvironment.__new__(BlenderEnvironment)

        instance.__init__()
        return instance


class BlenderEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/blender"
    DOCKER_TAG = "1.4"
    ENV_ID = "BLENDER"
    APP_DIR = path.join(get_golem_path(), 'apps', 'blender')
    SCRIPT_NAME = "docker_blendertask.py"
    SHORT_DESCRIPTION = "Blender (www.blender.org)"


class BlenderNVGPUEnvironment(BlenderEnvironment):
    DOCKER_IMAGE = "golemfactory/blender_nvgpu"
    DOCKER_TAG = "1.0"
    SHORT_DESCRIPTION = "Blender NVGPU (www.blender.org)"

    def supports_image(self, docker_image: DockerImage) -> bool:
        return super().supports_image(docker_image) or \
            super().DOCKER_IMAGE == docker_image.repository

    def get_volumes(self) -> List[str]:
        return [
            '/tmp/.X11-unix',
        ]

    def get_binds(self) -> Dict[str, Dict[str, str]]:
        return {
            posix_path('/tmp/.X11-unix'): {
                "bind": '/tmp/.X11-unix',
                "mode": "rw"
            }
        }

    def get_devices(self) -> List[str]:
        return [
            '/dev/nvidia0:/dev/nvidia0',
            '/dev/nvidiactl:/dev/nvidiactl',
            '/dev/nvidia-uvm:/dev/nvidia-uvm',
        ]

    def get_runtime(self) -> Optional[str]:
        return 'nvidia'
