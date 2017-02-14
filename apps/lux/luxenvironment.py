from os import path

from golem.core.common import get_golem_path
from golem.docker.image import DockerImage
from golem.docker.environment import DockerEnvironment
from golem.resource.dirmanager import find_task_script


class LuxRenderEnvironment(DockerEnvironment):
    LUXRENDER_DOCKER_IMAGE = "golemfactory/luxrender"
    LUXRENDER_DOCKER_TAG = "1.2"
    LUXRENDER_ID = "LUXRENDER"
    APP_DIR = path.join(get_golem_path(), 'apps', 'lux')
    SCRIPT_NAME = "docker_luxtask.py"

    @classmethod
    def get_id(cls):
        return cls.LUXRENDER_ID

    def __init__(self, tag=LUXRENDER_DOCKER_TAG, image_id=None):
        image = DockerImage(image_id=image_id) if image_id \
            else DockerImage(self.LUXRENDER_DOCKER_IMAGE, tag=tag)
        DockerEnvironment.__init__(self, [image])

        self.short_description = "LuxRender (www.luxrender.net)"
        self.main_program_file = find_task_script(self.APP_DIR, self.SCRIPT_NAME)

    def get_performance(self, cfg_desc):
        return cfg_desc.estimated_lux_performance
