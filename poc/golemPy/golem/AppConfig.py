import sys
sys.path.append('core')
import os
import logging

from golem.core.simpleconfig import SimpleConfig, ConfigEntry
from golem.core.simpleenv import SimpleEnv
from golem.core.prochelper import ProcessService

CONFIG_FILENAME = "app_cfg.ini"
ESTM_FILENAME = "minilight.ini"
MANAGER_PORT = 20301
ESTIMATED_DEFAULT = 2220.0
START_PORT = 40102
END_PORT = 60102
OPTIMAL_PEER_NUM = 10
DEFAULT_ROOT_PATH = "C:\\Sources\\golem\\poc\\golemPy\\examples\\gnr"

class CommonConfig:

    ##############################
    def __init__( self,
                  section = "Common",
                  rootPath = DEFAULT_ROOT_PATH,
                  managerPort = MANAGER_PORT,
                  startPort = START_PORT,
                  endPort = END_PORT,
                  optimalPeerNum = OPTIMAL_PEER_NUM):

        self._section = section

        ConfigEntry.createProperty( section, "optimal peer num",    optimalPeerNum,    self, "OptimalPeerNum" )
        ConfigEntry.createProperty( section, "start port",          startPort, self, "StartPort" )
        ConfigEntry.createProperty( section, "end port",            endPort, self, "EndPort" )
        ConfigEntry.createProperty( section, "manager listen port", managerPort, self, "ManagerListenPort" )
        ConfigEntry.createProperty( section, "resource root path", rootPath, self, "RootPath")

    ##############################
    def section( self ):
        return self._section


class NodeConfig:

    @classmethod
    def readEstimatedPerformance(cls):
        estmFile = SimpleEnv.envFileName(ESTM_FILENAME)
        res = 0
        if os.path.isfile(estmFile):
            try:
                file = open(estmFile, 'r')
                res = "{0:.1f}".format(float(file.read()))
                file.close()
            except:
                return 0
        return res

    ##############################
    def __init__( self, nodeId, seedHost = "", seedPort = 0, numCores = 4 ):
        self._section = "Node {}".format( nodeId )

        estimated = NodeConfig.readEstimatedPerformance()
        if estimated == 0:
            estimated = ESTIMATED_DEFAULT

        ConfigEntry.createProperty( self.section(), "seed host",           seedHost,    self, "SeedHost" )
        ConfigEntry.createProperty( self.section(), "seed host port",      seedPort,     self, "SeedHostPort")
        ConfigEntry.createProperty( self.section(), "send pings",          0,     self, "SendPings" )
        ConfigEntry.createProperty( self.section(), "pigns interval",      0,     self, "PingsInterval" )
        ConfigEntry.createProperty( self.section(), "client UUID",         u"",   self, "ClientUid" )
        ConfigEntry.createProperty( self.section(), "getting peers interval",   4.0,   self, "GettingPeersInterval" )
        ConfigEntry.createProperty( self.section(), "getting tasks interval",   4.0,   self, "GettingTasksInterval" )
        ConfigEntry.createProperty( self.section(), "task request interval",    5.0,   self, "TaskRequestInterval" )
        ConfigEntry.createProperty( self.section(), "estimated perfomance",  estimated,  self, "EstimatedPerformance" )
        ConfigEntry.createProperty( self.section(), "node snapshot interval",   4.0,  self, "NodeSnapshotInterval" )
        ConfigEntry.createProperty( self.section(), "add tasks",           0,     self, "AddTasks" )
        ConfigEntry.createProperty( self.section(), "maximum delay for sending task results",           3600,  self, "MaxResultsSendingDelay" )
        ConfigEntry.createProperty( self.section(), "number of cores", numCores, self, "NumCores")

    ##############################
    def section( self ):
        return self._section


##############################
##############################
class AppConfig:

    CONFIG_LOADED = False

    ##############################
    @classmethod
    def managerPort( cls ):
        return MANAGER_PORT

    ##############################
    @classmethod
    def loadConfig( cls, cfgFile = CONFIG_FILENAME ):

        logger = logging.getLogger(__name__)

        if cls.CONFIG_LOADED:
            logger.warning("Application already configured")
            return None


        logger.info("Starting generic process service...")
        ps = ProcessService()
        logger.info("Generic process service started")

        logger.info("Trying to register current process")
        localId = ps.registerSelf()

        if( localId < 0 ):
            logger.error("Failed to register current process - bailing out")
            return None

        cfg  = SimpleConfig( CommonConfig(), NodeConfig( localId ), cfgFile )

        cls.CONFIG_LOADED = True

        return AppConfig( cfg )

    ##############################
    def __init__( self, cfg ):
        self._cfg = cfg

    ##############################
    def getRootPath( self ):
        return self._cfg.getCommonConfig().getRootPath()

    def getOptimalPeerNum( self ):
        return self._cfg.getCommonConfig().getOptimalPeerNum()

    def getStartPort( self ):
        return self._cfg.getCommonConfig().getStartPort()

    def getEndPort( self ):
        return self._cfg.getCommonConfig().getEndPort()

    def getManagerListenPort( self ):
        return self._cfg.getCommonConfig().getManagerListenPort()

    def getSeedHost( self ):
        return self._cfg.getNodeConfig().getSeedHost()

    def getSeedHostPort( self ):
        return self._cfg.getNodeConfig().getSeedHostPort()

    def getSendPings( self ):
        return self._cfg.getNodeConfig().getSendPings()

    def getPingsInterval( self ):
        return self._cfg.getNodeConfig().getPingsInterval()

    def getClientUid( self ):
        return self._cfg.getNodeConfig().getClientUid()

    def getGettingPeersInterval( self ):
        return self._cfg.getNodeConfig().getGettingPeersInterval()

    def getGettingTasksInterval( self ):
        return self._cfg.getNodeConfig().getGettingTasksInterval()

    def getTaskRequestInterval( self ):
        return self._cfg.getNodeConfig().getTaskRequestInterval()

    def getEstimatedPerformance( self ):
        try:
            return float( self._cfg.getNodeConfig().getEstimatedPerformance() )
        except:
            return float( ESTIMATED_DEFAULT )

    def getNodeSnapshotInterval( self ):
        return self._cfg.getNodeConfig().getNodeSnapshotInterval()

    def getAddTasks( self ):
        return self._cfg.getNodeConfig().getAddTasks()

    def getMaxResultsSendingDelay( self ):
        return self._cfg.getNodeConfig().getMaxResultsSendingDelay()

    def getNumCores ( self ):
        return self._cfg.getNodeConfig().getNumCores()

    ##############################
    def changeConfig( self, seedHost, seedPort, rootPath, managerPort, numCores, cfgFile = CONFIG_FILENAME, ):
        self._cfg.getNodeConfig().setSeedHost( seedHost )
        self._cfg.getNodeConfig().setSeedHostPort( seedPort )
        self._cfg.getNodeConfig().setNumCores( numCores )
        self._cfg.getCommonConfig().setRootPath( rootPath )
        self._cfg.getCommonConfig().setManagerListenPort( managerPort )
        SimpleConfig( self._cfg.getCommonConfig(), self._cfg.getNodeConfig(), cfgFile, True )

    def __str__( self ):
        return str( self._cfg )

if __name__ == "__main__":

    c = AppConfig( 0 )
    print c
    c = AppConfig( 1 )
    print c
    c = AppConfig( 2 )
    print c
