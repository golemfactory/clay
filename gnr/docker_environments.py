from golem.task.docker.environment import DockerEnvironment
from golem.task.docker.image import DockerImage


class BlenderDockerEnvironment(DockerEnvironment):

    BLENDER_DOCKER_IMAGE = "golem/blender"

    @classmethod
    def get_id(cls):
        return "BLENDER"

    def __init__(self, tag="latest", id=None):
        image = DockerImage(id=id) if id \
            else DockerImage(self.BLENDER_DOCKER_IMAGE, tag=tag)
        DockerEnvironment.__init__(self, [image])

        self.short_description = "Blender (www.blender.org)"


class LuxRenderDockerEnvironment(DockerEnvironment):

    LUXRENDER_DOCKER_IMAGE = "golem/luxrender"

    @classmethod
    def get_id(cls):
        return "LUXRENDER"

    def __init__(self, tag="latest", id=None):
        image = DockerImage(id=id) if id \
            else DockerImage(self.LUXRENDER_DOCKER_IMAGE, tag=tag)
        DockerEnvironment.__init__(self, [image])

        self.short_description = "LuxRender (www.luxrender.net)"
