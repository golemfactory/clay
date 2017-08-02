from os import path

from golem.core.common import get_golem_path
from golem.docker.image import DockerImage
from golem.docker.environment import DockerEnvironment
from golem.resource.dirmanager import find_task_script

# TODO class copied from LuxEnvironment, do sth about it
# parameters should be abstract in the base class and required to be set
# but that will not be possible until python 3

class DummyTaskEnvironment(DockerEnvironment):
    DUMMYPOW_DOCKER_IMAGE = "golemfactory/base" # TODO change to golemfactory/dummy
    DUMMYPOW_DOCKER_TAG = "1.2"
    DUMMYPOW_ID = "DUMMYPOW"
    APP_DIR = path.join(get_golem_path(), 'apps', 'dummy')
    SCRIPT_NAME = "docker_dummytask.py"

    @classmethod
    def get_id(cls):
        return cls.DUMMYPOW_ID

    def __init__(self, tag=DUMMYPOW_DOCKER_TAG, image_id=None):
        image = DockerImage(image_id=image_id) if image_id \
            else DockerImage(self.DUMMYPOW_DOCKER_IMAGE, tag=tag)
        DockerEnvironment.__init__(self, [image])

        self.short_description = "Dummy task (example app calculating proof-of-work hash)"
        self.main_program_file = find_task_script(self.APP_DIR, self.SCRIPT_NAME)

    def get_performance(self, cfg_desc):
        return cfg_desc.estimated_dummy_performance