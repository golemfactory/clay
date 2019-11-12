from typing import Dict

from apps.core import nvgpu
from apps.core.nvgpu import get_devices
from golem.docker.environment import DockerEnvironment
from golem.docker.image import DockerImage
from golem.environments.environment import SupportStatus, UnsupportReason


class BlenderEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/blender"
    DOCKER_TAG = "1.13"
    ENV_ID = "BLENDER"
    SHORT_DESCRIPTION = "Blender (www.blender.org)"


class BlenderNVGPUEnvironment(BlenderEnvironment):

    DOCKER_IMAGE = "golemfactory/blender_nvgpu"
    DOCKER_TAG = "1.7"
    ENV_ID = "BLENDER_NVGPU"
    SHORT_DESCRIPTION = "Blender + NVIDIA GPU (www.blender.org)"

    def __init__(self) -> None:
        super().__init__(additional_images=[DockerImage(
            repository=BlenderEnvironment.DOCKER_IMAGE,
            tag=BlenderEnvironment.DOCKER_TAG,
        )])

    def check_support(self) -> SupportStatus:
        if not nvgpu.is_supported():
            return SupportStatus.err({
                UnsupportReason.ENVIRONMENT_UNSUPPORTED: self.ENV_ID
            })
        return super().check_support()

    def get_container_config(self) -> Dict:
        return dict(
            runtime='nvidia',
            volumes=[],
            binds={},
            devices=[],
            environment={
                'NVIDIA_VISIBLE_DEVICES': ','.join(map(str, get_devices())),
                'BLENDER_DEVICE_TYPE': 'nvidia_gpu',
            },
        )
