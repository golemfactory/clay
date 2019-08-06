import abc
from typing import List, Dict

import enforce

from golem.docker.image import DockerImage
from golem.environments.environment import (Environment, SupportStatus,
                                            UnsupportReason)


@enforce.runtime_validation()
class DockerEnvironment(Environment, metaclass=abc.ABCMeta):
    # pylint: disable=no-self-use

    def __init__(self, tag=None, image_id=None, additional_images: List[DockerImage] = None):

        if tag is None:
            tag = self.DOCKER_TAG

        image = DockerImage(image_id=image_id) if image_id \
            else DockerImage(self.DOCKER_IMAGE, tag=tag)
        Environment.__init__(self)

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

    def supports_image(self, docker_image: DockerImage) -> bool:
        return any(image.repository == docker_image.repository
                   for image in self.docker_images)

    def description(self):
        descr = Environment.description(self)

        descr += "DOCKER IMAGES (any of):\n"
        for img in self.docker_images:
            descr += "\t * " + img.name + "\n"
        descr += "\n"

        return descr

    def get_container_config(self) -> Dict:
        return dict(
            runtime=None,
            volumes=[],
            binds={},
            devices=[],
            environment={},
        )

    @property
    @abc.abstractmethod
    def DOCKER_IMAGE(cls):
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def DOCKER_TAG(cls):
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def ENV_ID(cls):
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def SHORT_DESCRIPTION(cls):
        raise NotImplementedError

    @classmethod
    def get_id(cls):
        return cls.ENV_ID
