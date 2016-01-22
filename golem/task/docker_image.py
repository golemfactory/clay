from docker import Client
from docker.errors import NotFound


class DockerImage(object):

    def __init__(self, repository, id=None, tag=None):
        self.repository = repository
        self.id = id
        self.tag = tag if tag else "latest"

    def is_available(self):
        client = Client()
        try:
            if self.id:
                info = client.inspect_image(self.id)
                return info and info["Id"] == self.id
            else:
                full_name = "{}:{}".format(self.repository, self.tag)
                info = client.inspect_image(full_name)
                return info and full_name in info["RepoTags"]
        except NotFound:
            return None





