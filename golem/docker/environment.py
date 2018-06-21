import abc
from typing import List

import enforce

from golem.docker.image import DockerImage
from golem.docker.task_thread import DockerTaskThread
from golem.environments.environment import (Environment, SupportStatus,
                                            UnsupportReason)
from golem.resource.dirmanager import find_task_script


@enforce.runtime_validation()
class DockerEnvironment(Environment):
    def __init__(self, tag=None, image_id=None,
                 additional_images: List[DockerImage] = None) -> None:

        if tag is None:
            tag = self.DOCKER_TAG

        image = DockerImage(image_id=image_id) if image_id \
            else DockerImage(self.DOCKER_IMAGE, tag=tag)
        Environment.__init__(self)
        self.software.append('Docker')

        self.default_program_file = find_task_script(self.APP_DIR,
                                                     self.SCRIPT_NAME)
        self.source_code_required = True
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

    # pylint: disable=too-many-arguments
    def get_task_thread(self, taskcomputer, subtask_id, short_desc,
                        src_code, extra_data, task_timeout,
                        working_dir, resource_dir, temp_dir, **kwargs):
        prepared_params = self.prepare_params(extra_data)
        return DockerTaskThread(taskcomputer, subtask_id, self.docker_images,
                                working_dir, src_code, prepared_params,
                                short_desc, resource_dir, temp_dir,
                                task_timeout, **kwargs)

    # pylint: disable=no-self-use
    def prepare_params(self, extra_data):
        """
        Prepare extra_data from CDT for docker execution. The way they
        might be modified is depending on specifics on each docker job
        implementation.
        :param extra_data:
        :return: modified extra_data
        """
        return extra_data

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
