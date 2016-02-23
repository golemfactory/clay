from client import local_client
from docker import errors


class DockerImage(object):

    def __init__(self, repository, id=None, tag=None):
        self.repository = repository
        self.id = id
        self.tag = tag if tag else "latest"
        self.name = "{}:{}".format(self.repository, self.tag)

    def is_available(self):
        client = local_client()
        try:
            if self.id:
                info = client.inspect_image(self.id)
                return self.name in info["RepoTags"]
            else:
                info = client.inspect_image(self.name)
                return self.id is None or info["Id"] == self.id
        except errors.NotFound:
            return False
        except errors.APIError as e:
            if self.tag is not None:
                return False
            raise e
        except ValueError:
            return False
