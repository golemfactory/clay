import abc
from typing import List

import enforce

from golem.docker.image import DockerImage
from golem.environments.environment import (Environment, SupportStatus,
                                            UnsupportReason)
from golem.resource.dirmanager import find_task_script


@enforce.runtime_validation()
class DockerEnvironment(Environment, metaclass=abc.ABCMeta):
    def __init__(self, tag=None, image_id=None, additional_images: List[DockerImage] = None):

        if tag is None:
            tag = self.DOCKER_TAG

        image = DockerImage(image_id=image_id) if image_id \
            else DockerImage(self.DOCKER_IMAGE, tag=tag)
        Environment.__init__(self)
        self.software.append('Docker')

        self.main_program_file = find_task_script(self.APP_DIR, self.SCRIPT_NAME)

        self.docker_images = [image]
        if additional_images:
            self.docker_images += additional_images

        if self.SHORT_DESCRIPTION:
            self.short_description = self.SHORT_DESCRIPTION

    def check_docker_images(self) -> SupportStatus:
        if any(img.is_available() for img in self.docker_images):
            return SupportStatus.ok()

        return SupportStatus.err({UnsupportReason.ENVIRONMENT_UNSUPPORTED: {
            'env_id': self.get_id(),
            'docker_images_missing_any': self.docker_images,
        }})

    def check_support(self) -> SupportStatus:
        return self.check_docker_images().join(Environment.check_support(self))

    def description(self):
        descr = Environment.description(self)

        descr += "DOCKER IMAGES (any of):\n"
        for img in self.docker_images:
            descr += "\t * " + img.name + "\n"
        descr += "\n"

        return descr

    @property
    @abc.abstractmethod
    def DOCKER_IMAGE(cls):
        pass

    @property
    @abc.abstractmethod
    def DOCKER_TAG(cls):
        pass

    @property
    @abc.abstractmethod
    def ENV_ID(cls):
        pass

    @property
    @abc.abstractmethod
    def APP_DIR(cls):
        pass

    @property
    @abc.abstractmethod
    def SCRIPT_NAME(cls):
        pass

    @property
    @abc.abstractmethod
    def SHORT_DESCRIPTION(cls):
        pass

    @classmethod
    def get_id(cls):
        return cls.ENV_ID
