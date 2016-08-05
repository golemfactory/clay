import logging

from golem.docker.image import DockerImage
from golem.docker.environment import DockerEnvironment

logger = logging.getLogger("gnr.app")


class BlenderEnvironment(DockerEnvironment):

    BLENDER_DOCKER_IMAGE = "golem/blender"

    @classmethod
    def get_id(cls):
        return "BLENDER"

    def __init__(self, tag="latest", image_id=None):
        image = DockerImage(image_id=id) if image_id \
            else DockerImage(self.BLENDER_DOCKER_IMAGE, tag=tag)
        DockerEnvironment.__init__(self, [image])

        self.short_description = "Blender (www.blender.org)"
    
    def get_performance(self, cfg_desc):
        return cfg_desc.estimated_blender_performance

class LuxRenderEnvironment(DockerEnvironment):

    LUXRENDER_DOCKER_IMAGE = "golem/luxrender"

    @classmethod
    def get_id(cls):
        return "LUXRENDER"

    def __init__(self, tag="latest", image_id=None):
        image = DockerImage(image_id=image_id) if image_id \
            else DockerImage(self.LUXRENDER_DOCKER_IMAGE, tag=tag)
        DockerEnvironment.__init__(self, [image])

        self.short_description = "LuxRender (www.luxrender.net)"
        
    def get_performance(self, cfg_desc):
        return cfg_desc.estimated_lux_performance
