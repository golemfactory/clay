from os import path

from golem.core.common import get_golem_path
from golem.docker.environment import DockerEnvironment


class BlenderEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/blender"
    DOCKER_TAG = "1.3"
    IMAGE_ID = "BLENDER"
    APP_DIR = path.join(get_golem_path(), 'apps', 'blender')
    SCRIPT_NAME = "docker_blendertask.py"
    SHORT_DESCRIPTION = "Blender (www.blender.org)"

    def get_performance(self, cfg_desc):
        return cfg_desc.estimated_blender_performance
