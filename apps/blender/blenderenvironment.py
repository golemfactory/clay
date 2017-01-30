from os import path

from golem.core.common import get_golem_path
from golem.docker.image import DockerImage
from golem.docker.environment import DockerEnvironment
from golem.resource.dirmanager import find_task_script


class BlenderEnvironment(DockerEnvironment):

    BLENDER_DOCKER_IMAGE = "golemfactory/blender"
    BLENDER_DOCKER_TAG = "1.3"
    BLENDER_ID = "BLENDER"
    APP_DIR = path.join(get_golem_path(), 'apps', 'blender')
    SCRIPT_NAME = "docker_blendertask.py"

    @classmethod
    def get_id(cls):
        return cls.BLENDER_ID

    def __init__(self, tag=BLENDER_DOCKER_TAG, image_id=None):
        image = DockerImage(image_id=id) if image_id \
            else DockerImage(self.BLENDER_DOCKER_IMAGE, tag=tag)
        DockerEnvironment.__init__(self, [image])

        self.short_description = "Blender (www.blender.org)"
        self.main_program_file = find_task_script(self.APP_DIR, self.SCRIPT_NAME)

    def get_performance(self, cfg_desc):
        return cfg_desc.estimated_blender_performance



