from os import path, environ

from golem.docker.image import DockerImage
from golem.docker.environment import DockerEnvironment


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

        self.software_env_variables = ['LUXRENDER_ROOT']
        if self.is_windows():
            self.software_name = ['luxconsole.exe', 'luxmerger.exe']
        else:
            self.software_name = ['luxconsole', 'luxmerger']
        self.lux_console_path = ''
        self.lux_merger_path = ''

    def check_software(self):
        lux_installed = False
        for var in self.software_env_variables:
            lux_path = environ.get(var)
            if lux_path:
                self.lux_console_path = path.join(lux_path, self.software_name[0])
                self.lux_merger_path = path.join(lux_path, self.software_name[1])
                if path.isfile(self.lux_console_path) and path.isfile(self.lux_merger_path):
                    lux_installed = True

        return lux_installed

    def get_lux_console(self):
        self.check_software()
        if path.isfile(self.lux_console_path):
            return self.lux_console_path
        else:
            return ""

    def get_lux_merger(self):
        self.check_software()
        if path.isfile(self.lux_merger_path):
            return self.lux_merger_path
        else:
            return ""
