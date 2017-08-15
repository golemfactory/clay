from os import path

from golem.core.common import get_golem_path
from golem.docker.environment import DockerEnvironment


class LuxRenderEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/luxrender"
    DOCKER_TAG = "1.2"
    IMAGE_ID = "LUXRENDER"
    APP_DIR = path.join(get_golem_path(), 'apps', 'lux')
    SCRIPT_NAME = "docker_luxtask.py"
    SHORT_DESCRIPTION = "LuxRender (www.luxrender.net)"

    def get_performance(self, cfg_desc):
        return cfg_desc.estimated_lux_performance
