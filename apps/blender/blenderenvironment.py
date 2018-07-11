from os import environ, path
from typing import Tuple, List, Dict

from apps.core import nvgpu
from golem.core.common import get_golem_path
from golem.docker.environment import DockerEnvironment


def _get_image_and_tag(gpu_supported: bool) -> Tuple[str, str]:
    if gpu_supported:
        return "golemfactory/blender_nvgpu", "1.0"
    return "golemfactory/blender", "1.4"


class BlenderEnvironment(DockerEnvironment):
    ENV_ID = "BLENDER"

    GPU_SUPPORTED = nvgpu.is_supported()
    GPU_ENV = {
        'DISPLAY': environ.get("DISPLAY"),
    }
    GPU_VOLUMES = [
        '/tmp/.X11-unix:/tmp/.X11-unix',
    ]
    GPU_DEVICES = [
        '/dev/nvidia0:/dev/nvidia0',
        '/dev/nvidiactl:/dev/nvidiactl',
        '/dev/nvidia-uvm:/dev/nvidia-uvm',
    ]

    DOCKER_IMAGE, DOCKER_TAG = _get_image_and_tag(GPU_SUPPORTED)
    APP_DIR = path.join(get_golem_path(), 'apps', 'blender')
    SCRIPT_NAME = "docker_blendertask.py"
    SHORT_DESCRIPTION = "Blender (www.blender.org)"

    def get_volumes(self) -> List[str]:
        if not self.GPU_SUPPORTED:
            return super().get_volumes()
        return self.GPU_VOLUMES

    def get_devices(self) -> List[str]:
        if not self.GPU_SUPPORTED:
            return super().get_devices()
        return self.GPU_DEVICES

    def get_environment_variables(self) -> Dict[str, str]:
        if not self.GPU_SUPPORTED:
            return super().get_environment_variables()
        return self.GPU_ENV
