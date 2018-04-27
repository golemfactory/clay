import logging
import requests.exceptions

from docker.errors import NotFound, APIError

from .client import local_client

log = logging.getLogger(__name__)


class DockerImage(object):

    def __init__(self, repository=None, image_id=None, tag=None):
        self.repository = repository
        self.id = image_id
        self.tag = tag if tag else "latest"
        self.name = "{}:{}".format(self.repository, self.tag)

    def cmp_name_and_tag(self, docker_image):
        return docker_image.name == self.name and docker_image.tag == self.tag

    def __repr__(self):
        return ("DockerImage(repository={repository},"
                " image_id={id}, tag={tag})").format(**self.__dict__)

    def to_dict(self):
        return {
            'repository': self.repository,
            'image_id': self.id,
            'tag': self.tag,
        }

    def is_available(self):
        client = local_client()
        try:
            if self.id:
                info = client.inspect_image(self.id)
                return self.name in info["RepoTags"]
            info = client.inspect_image(self.name)
            return self.id is None or info["Id"] == self.id
        except NotFound:
            log.debug('DockerImage NotFound', exc_info=True)
            return False
        except APIError:
            log.debug('DockerImage APIError', exc_info=True)
            if self.tag is not None:
                return False
            raise
        except ValueError:
            log.debug('DockerImage ValueError', exc_info=True)
            return False
        except requests.exceptions.ConnectionError:
            log.debug("DockerImage Can't connect", exc_info=True)
            return False
