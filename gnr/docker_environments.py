from golem.task.docker.environment import DockerEnvironment
from golem.task.docker.image import DockerImage


class BlenderDockerEnvironment(DockerEnvironment):
    @classmethod
    def get_id(cls):
        return "BLENDER@DOCKER"

    def __init__(self, tag = "latest", id = None):
        image = DockerImage(id = id) if id \
            else DockerImage("golem/blender", tag = tag)
        DockerEnvironment.__init__(self, [image])

        self.short_description = "Blender (http://www.blender.org/) " \
                                 "running inside a Docker container"
