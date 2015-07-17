import ConfigParser

import os
import shutil
import types
import inspect
import logging

from simpleauth import SimpleAuth
from simpleenv import SimpleEnv

##############################
##############################
logger = logging.getLogger(__name__)

##############################
class ConfigEntry:

    def __init__(self, section, key, value):
        self._key = key
        self._value = value
        self._section = section
        self._valueType = type(value)

    def section(self):
        return self._section

    def key(self):
        return self._key

    def value(self):
        return self._value

    def setKey(self, k):
        self._key = k

    def setValue(self, v):
        self._value = v

    def setValueFromStr(self, val):
        self.setValue(self._valueType(val))

    def __str__(self):
        return "Section {0._section:7} prop: {0._key:17} -> {0._value:10} {0._valueType}".format(self)

    @classmethod
    def createProperty(cls, section, key, value, other, propName):
        property = ConfigEntry(section, key, value)

        getterName = "get{}".format(propName)
        setterName = "set{}".format(propName)

        def getProp(_self):
            return getattr(_self, propName).value()

        def setProp(_self, val):
            return getattr(_self, propName).setValue(val)

        def getProperties(_self):
            return getattr(_self, '_properties')

        setattr(other.__class__, propName, property)
        setattr(other.__class__, getterName, getProp)
        setattr(other.__class__, setterName, setProp)

        if not hasattr(other.__class__, 'properties'):
            setattr(other.__class__, '_properties', [])
            setattr(other.__class__, 'properties', getProperties)

        getattr(other.__class__, '_properties').append(getattr(other.__class__, propName))


##############################
##############################
class SimpleConfig:

    ##############################
    def __init__(self, commonConfig, nodeConfig, cfgFile, refresh = False, checkUid = True):

        self._commonConfig  = commonConfig
        self._nodeConfig    = nodeConfig

        cfgFile = SimpleEnv.envFileName(cfgFile)

        loggerMsg = "Reading config from file {}".format(cfgFile)

        try:
            writeConfig = True
            cfg = ConfigParser.ConfigParser()
            files = cfg.read(cfgFile)

            if len(files) == 1 and self._commonConfig.section() in cfg.sections():
                if self._nodeConfig.section() in cfg.sections():
                    if refresh:
                        cfg.remove_section(self._nodeConfig.section())
                        cfg.add_section(self._nodeConfig.section())
                    else:
                        self.__readOptions(cfg)

                        if not checkUid:
                            writeConfig = False
                        elif len(self._nodeConfig.getClientUid()) > 0:
                            writeConfig = False
                else:
                    cfg.add_section(self._nodeConfig.section())

                logger.info("{} ... successfully".format(loggerMsg))
            else:
                logger.info("{} ... failed".format(loggerMsg))
                cfg = self.__createFreshConfig()

            if writeConfig:
                logger.info("Writing {}'s configuration to {}".format(self.getNodeConfig().section(), cfgFile))
                self.__writeConfig(cfg, cfgFile, checkUid)
        except Exception as ex:
            logger.warning("{} ... failed with an exception: {}".format(loggerMsg, str(ex)))
            #no additional try catch because this cannot fail (if it fails then the program shouldn't start anyway)
            logger.info("Failed to write configuration file. Creating fresh config.")
            self.__writeConfig(self.__createFreshConfig(), cfgFile, checkUid)

    ##############################
    def getCommonConfig(self):
        return self._commonConfig

    ##############################
    def getNodeConfig(self):
        return self._nodeConfig

    ##############################
    def __createFreshConfig(self):
        cfg = ConfigParser.ConfigParser()
        cfg.add_section(self.getCommonConfig().section())
        cfg.add_section(self.getNodeConfig().section())

        return cfg

    ##############################
    def __writeConfig(self, cfg, cfgFile, uuid):
        if uuid:
            loggerMsg = "Generating fresh UUID for {} ->".format(self.getNodeConfig().section())
            uajdi = SimpleAuth.generateUUID()
            logger.info("{} {}".format(loggerMsg, uajdi.get_hex()))
            self.getNodeConfig().setClientUid(uajdi.get_hex())

        self.__writeOptions(cfg)
   
        if os.path.exists(cfgFile):
            backupFileName = "{}.bak".format(cfgFile)
            logger.info("Creating backup configuration file {}".format(backupFileName))
            shutil.copy(cfgFile, backupFileName)

        with open(cfgFile, 'w') as f:
            cfg.write(f)

    ##############################
    def __readOption(self, cfg, property):
        return cfg.get(property.section(), property.key())

    ##############################
    def __writeOption(self, cfg, property):
        return cfg.set(property.section(), property.key(), property.value())

    ##############################
    def __readOptions(self, cfg):

        for prop in self.getCommonConfig().properties() + self.getNodeConfig().properties():
            prop.setValueFromStr(self.__readOption(cfg, prop))

    ##############################
    def __writeOptions(self, cfg):

        for prop in self.getCommonConfig().properties() + self.getNodeConfig().properties():
            self.__writeOption(cfg, prop)

    ##############################
    def __str__(self):
        rs = "DefaultConfig\n"

        for prop in self.getCommonConfig().properties() + self.getNodeConfig().properties():
            rs += "{}\n".format(str(prop))

        return rs

if __name__ == "__main__":

    # get a list of a class's method type attributes
    def listattr(c):
        for m in [(n, v) for n, v in inspect.getmembers(c, inspect.ismethod) if isinstance(v,types.MethodType)]:
            print m[0], m[1]

    #c = DefaultConfig(0)
    #print c
    #c = DefaultConfig(1)
    #print c
    #c = DefaultConfig(2)
    #print c
#    c = GlobalConfig()
    
#    listattr(c)

#    print c.getOptimalPeerNum()
#    c.setOptimalPeerNum(20)
#    print c.getOptimalPeerNum()

#    cfg = DefaultConfig(0, "some_test_cfg.ini")
#    cfg1 = DefaultConfig(1, "some_test_cfg.ini")
#    cfg2 = DefaultConfig(2, "some_test_cfg.ini")
