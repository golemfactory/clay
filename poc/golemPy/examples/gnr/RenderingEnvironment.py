import os
import shutil
import logging

from golem.environments.Environment import Environment
from golem.environments.checkCmd import checkCmd

from examples.gnr.task.ThreeDSMaxCfgEditor import regenerateFile


logger = logging.getLogger(__name__)

###########################################################################
class ThreeDSMaxEnvironment(Environment):
    #########################
    @classmethod
    def getId(cls):
        return "3DSMAX"

    #########################
    def __init__(self):
        Environment.__init__(self)
        self.software.append('3DS Max Studio 2014 or 3DS Max Studio 2015')
        self.software.append('Windows')
        self.softwareEnvVar = ['ADSK_3DSMAX_x64_2015', 'ADSK_3DSMAX_x32_2015', 'ADSK_3DSMAX_x64_2014', 'ADSK_3DSMAX_x32_2014']
        self.softwareName = '3dsmaxcmd.exe'
        self.configFileName = 'plugcfg_ln/mentalray_cpu.ini'
        self.configFileBackup = 'plugcfg_ln/mentalray_cpu.bak'
        self.shortDescription = "3DS MAX Studio command tool (http://www.autodesk.pl/products/3ds-max/overview)"
        self.path = ""

    #########################
    def checkSoftware(self):
        if not self.is_windows():
            return False
        for var in self.softwareEnvVar:
            if os.environ.get(var):
                self.path = os.path.join(os.environ.get(var), '3dsmaxcmd.exe')
                if os.path.isfile(self.path):
                    return True
        return False

    #########################
    def supported(self) :
        return self.checkSoftware()

    #########################
    def get3dsmaxcmdPath (self):
        self.checkSoftware()
        if os.path.isfile(self.path):
            return self.path
        else:
            return ""

    #########################
    def setNThreads(self, num_cores):
        for var in self.softwareEnvVar:
            if os.environ.get(var):
                self.__rewriteCfgFile(var, num_cores)

    #########################
    def __rewriteCfgFile(self, var, num_cores):
        path = os.path.join(os.environ.get(var), self.configFileName)
        backupPath = os.path.join(os.environ.get(var), self.configFileBackup)
        logger.debug("Cfg file: {}, numThreads = {}".format(path, num_cores))
        if os.path.isfile(path):
            with open(path, 'r') as f:
                cfgSrc = f.read()
            shutil.copy2(path, backupPath)
            newCfg = regenerateFile(cfgSrc, num_cores)
            with open(path, 'w') as f:
                f.write(newCfg)
            return

    #########################
    def getDefaultPreset(self):
        for var in self.softwareEnvVar:
            if os.environ.get(var):
                presetFile = os.path.join(os.environ.get(var), 'renderpresets\mental.ray.daylighting.high.rps')
                if os.path.isfile(presetFile):
                    return presetFile
        return ""

###########################################################################
class PBRTEnvironment (Environment):
    #########################
    @classmethod
    def getId(cls):
        return "PBRT"

    #########################
    def __init__(self):
        Environment.__init__(self)
        self.shortDescription =  "PBRT renderer (http://www.pbrt.org/)  "

    #########################
    def supported(self) :
        return True

###########################################################################
class VRayEnvironment(Environment):
    #########################
    @classmethod
    def getId(cls):
        return "VRAY"

    #########################
    def __init__(self):
        Environment.__init__(self)
        self.software.append('V-Ray standalone')
        self.shortDescription = "V-Ray Renderer (http://www.vray.com/)"
        self.softwareEnvVariable = 'VRAY_PATH'
        if self.is_windows():
            self.softwareName = 'vray.exe'
        else:
            self.softwareName = 'vray'
        self.path = ""

    #########################
    def checkSoftware(self):
        if os.environ.get(self.softwareEnvVariable):
            self.path = os.path.join(os.environ.get(self.softwareEnvVariable), self.softwareName)
            if os.path.isfile(self.path):
                return True
        return False

    #########################
    def supported(self):
        return self.checkSoftware()

    #########################
    def getCmdPath (self):
        self.checkSoftware()
        if os.path.isfile(self.path):
            return self.path
        else:
            return ""

###########################################################################
class LuxRenderEnvironment(Environment):
    #########################
    @classmethod
    def getId(cls):
        return "LUXRENDER"

    #########################
    def __init__(self):
        Environment.__init__(self)
        self.software.append('LuxRender')
        self.shortDescription = "LuxRenderer Renderer (http://www.luxrender.net/)"
        self.softwareEnvVariables = ['LUXRENDER_ROOT']
        if self.is_windows():
            self.softwareName = ['luxconsole.exe', 'luxmerger.exe']
        else:
            self.softwareName = ['luxconsole', 'luxmerger']
        self.luxConsolePath = ''
        self.luxMergerPath = ''

    #########################
    def checkSoftware(self):
        luxInstalled = False
        for var in self.softwareEnvVariables:
            if os.environ.get(var):
                self.luxConsolePath = os.path.join(os.environ.get(var), self.softwareName[0])
                self.luxMergerPath = os.path.join(os.environ.get(var), self.softwareName[1])
                if os.path.isfile(self.luxConsolePath) and os.path.isfile(self.luxMergerPath):
                    luxInstalled = True

        return luxInstalled

    #########################
    def supported(self):
        return self.checkSoftware()

    #########################
    def getLuxConsole(self):
        self.checkSoftware()
        if os.path.isfile(self.luxConsolePath):
            return self.luxConsolePath
        else:
            return ""

    #########################
    def getLuxMerger(self):
        self.checkSoftware()
        if os.path.isfile(self.luxMergerPath):
            return self.luxMergerPath
        else:
            return ""

###########################################################################
class BlenderEnvironment(Environment):
    #########################
    @classmethod
    def getId(cls):
        return "Blender"

    #########################
    def __init__(self):
        Environment.__init__(self)
        self.software.append('Blender')
        self.shortDescription = "Blender (http://www.blender.org/)"
        self.softwareName = 'blender'

    #########################
    def supported(self):
        return self.checkSoftware()

    #########################
    def checkSoftware(self):
        return checkCmd(self.softwareName)

    #########################
    def getBlender(self):
        return self.softwareName