from golem.core.simpleenv import SimpleEnv
from golem.core.simpleconfig import SimpleConfig, ConfigEntry
import logging

ENV_VERSION = 1.01
CONFIG_FILENAME = "environments.ini"

logger = logging.getLogger(__name__)

############################################################
class CommonConfig:
    ##############################
    def __init__(self,
                 section = "Common",
                 envVersion = ENV_VERSION):

        self._section = section

        ConfigEntry.createProperty( section, "environment version", envVersion, self, "envVersion" )

    ##############################
    def section( self ):
        return self._section

############################################################
class NodeConfig:
    ##############################
    def __init__( self, nodeId, environments = []):
        self._section = "Node {}".format( nodeId )

        for envId, (envName, supported) in environments.iteritems():
            ConfigEntry.createProperty( self.section(), envId.lower(), int( supported ), self, envName )

    ##############################
    def section( self ):
        return self._section

############################################################
class EnvironmentsConfig:

    ##############################
    @classmethod
    def loadConfig( cls, nodeId, environments, cfgFile = CONFIG_FILENAME ):

        cfg  = SimpleConfig( CommonConfig(), NodeConfig( nodeId, environments ), cfgFile, refresh = False, checkUid = False )

        return EnvironmentsConfig( cfg )

    ##############################
    def __init__( self, cfg ):
        self._cfg = cfg

    ##############################
    def getConfigEntries(self):
        return self._cfg.getNodeConfig()

    ##############################
    def changeConfig( self, cfgFile = CONFIG_FILENAME ):
        return EnvironmentsConfig( SimpleConfig( self._cfg.getCommonConfig(), self._cfg.getNodeConfig(), cfgFile,  refresh = True, checkUid = False ) )

    ##############################
    def __str__( self ):
        return str( self._cfg )
