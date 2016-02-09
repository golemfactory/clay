from docker import Client
from docker import errors


class DockerImage(object):

    def __init__(self, repository, id=None, tag=None):
        self.repository = repository
        self.id = id
        self.tag = tag if tag else "latest"
        self.name = "{}:{}".format(self.repository, self.tag)
        if not self._check():
            raise ValueError("Image name does not match image ID")

    def _check(self):
        client = Client()
        if self.id:
            info = client.inspect_image(self.id)
        else:
            info = client.inspect_image(self.name)
        # Check that name and ID agree
        assert info
        return self.name in info["RepoTags"] and (
            self.id is None or info["Id"] == self.id)

    @staticmethod
    def is_available(repository, id=None, tag=None):
        try:
            image = DockerImage(repository, id=id, tag=tag)
            return image._check()
        except errors.NotFound:
            return False
        except errors.APIError as e:
            if tag is not None:
                return False
            raise e
        except ValueError:
            return False
