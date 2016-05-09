import logging
import os
import shutil


from golem.docker.image import DockerImage
from golem.docker.environment import DockerEnvironment
from golem.environments.environment import Environment

from gnr.task.threedsmaxcfgeditor import regenerate_file

logger = logging.getLogger(__name__)


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


class ThreeDSMaxEnvironment(Environment):
    @classmethod
    def get_id(cls):
        return "3DSMAX"

    def __init__(self):
        Environment.__init__(self)
        self.software.append('3DS Max Studio 2014 or 3DS Max Studio 2015')
        self.software.append('Windows')
        self.software_env_var = ['ADSK_3DSMAX_x64_2015', 'ADSK_3DSMAX_x32_2015', 'ADSK_3DSMAX_x64_2014',
                                 'ADSK_3DSMAX_x32_2014']
        self.software_name = '3dsmaxcmd.exe'
        self.config_file_name = 'plugcfg_ln/mentalray_cpu.ini'
        self.config_file_backup = 'plugcfg_ln/mentalray_cpu.bak'
        self.short_description = "3DS MAX Studio command tool (http://www.autodesk.pl/products/3ds-max/overview)"
        self.path = ""

    def check_software(self):
        if not self.is_windows():
            return False
        for var in self.software_env_var:
            if os.environ.get(var):
                self.path = os.path.join(os.environ.get(var), '3dsmaxcmd.exe')
                if os.path.isfile(self.path):
                    return True
        return False

    def supported(self):
        return self.check_software()

    def get_3ds_max_cmd_path(self):
        self.check_software()
        if os.path.isfile(self.path):
            return self.path
        else:
            return ""

    def set_n_threads(self, num_cores):
        for var in self.software_env_var:
            if os.environ.get(var):
                self.__rewrite_cfg_file(var, num_cores)

    def __rewrite_cfg_file(self, var, num_cores):
        path = os.path.join(os.environ.get(var), self.config_file_name)
        backup_path = os.path.join(os.environ.get(var), self.config_file_backup)
        logger.debug("Cfg file: {}, num_threads = {}".format(path, num_cores))
        if os.path.isfile(path):
            with open(path, 'r') as f:
                cfg_src = f.read()
            shutil.copy2(path, backup_path)
            new_cfg = regenerate_file(cfg_src, num_cores)
            with open(path, 'w') as f:
                f.write(new_cfg)
            return

    def get_default_preset(self):
        for var in self.software_env_var:
            if os.environ.get(var):
                preset_file = os.path.join(os.environ.get(var), 'renderpresets\mental.ray.daylighting.high.rps')
                if os.path.isfile(preset_file):
                    return preset_file
        return ""


class PBRTEnvironment(Environment):
    @classmethod
    def get_id(cls):
        return "PBRT"

    def __init__(self):
        Environment.__init__(self)
        self.software.append('Windows')
        self.short_description = "PBRT renderer (http://www.pbrt.org/)  "

    def supported(self):
        return self.is_windows()


class VRayEnvironment(Environment):
    @classmethod
    def get_id(cls):
        return "VRAY"

    def __init__(self):
        Environment.__init__(self)
        self.software.append('V-Ray standalone')
        self.short_description = "V-Ray Renderer (http://www.vray.com/)"
        self.software_env_variable = 'VRAY_PATH'
        if self.is_windows():
            self.software_name = 'vray.exe'
        else:
            self.software_name = 'vray'
        self.path = ""

    def check_software(self):
        if os.environ.get(self.software_env_variable):
            self.path = os.path.join(os.environ.get(self.software_env_variable), self.software_name)
            if os.path.isfile(self.path):
                return True
        return False

    def supported(self):
        return self.check_software()

    def get_cmd_path(self):
        self.check_software()
        if os.path.isfile(self.path):
            return self.path
        else:
            return ""
