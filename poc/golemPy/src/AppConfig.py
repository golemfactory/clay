
import sys
sys.path.append('core')

from simpleconfig import SimpleConfig, ConfigEntry
from prochelper import ProcessService

CONFIG_FILENAME = "app_cfg.ini"
MANAGER_PORT = 20301

class CommonConfig:

    ##############################
    def __init__( self, section = "Common" ):

        self._section = section

        ConfigEntry.createProperty( section, "optimal peer num",    10,    self, "OptimalPeerNum" )
        ConfigEntry.createProperty( section, "start port",          40102, self, "StartPort" )
        ConfigEntry.createProperty( section, "end port",            60102, self, "EndPort" )
        ConfigEntry.createProperty( section, "manager listen port", MANAGER_PORT, self, "ManagerListenPort" )

    ##############################
    def section( self ):
        return self._section


class NodeConfig:

    ##############################
    def __init__( self, nodeId ):
        self._section = "Node {}".format( nodeId )

        ConfigEntry.createProperty( self.section(), "seed host",           "",    self, "SeedHost" )
        ConfigEntry.createProperty( self.section(), "seed host port",      0,     self, "SeedHostPort")
        ConfigEntry.createProperty( self.section(), "send pings",          0,     self, "SendPings" )
        ConfigEntry.createProperty( self.section(), "pigns interval",      0,     self, "PingsInterval" )
        ConfigEntry.createProperty( self.section(), "client UUID",         u"",   self, "ClientUuid" )
        ConfigEntry.createProperty( self.section(), "getting peers interval",   4.0,   self, "GettingPeersInterval" )
        ConfigEntry.createProperty( self.section(), "getting tasks interval",   4.0,   self, "GettingTasksInterval" )
        ConfigEntry.createProperty( self.section(), "task request interval",    5.0,   self, "TaskRequestInterval" )
        ConfigEntry.createProperty( self.section(), "estimated perfomance",  2200.0,  self, "EstimatedPerformance" )
        ConfigEntry.createProperty( self.section(), "node snapshot interval",   4.0,  self, "NodeSnapshotInterval" )
        ConfigEntry.createProperty( self.section(), "add tasks",           0,     self, "AddTasks" )

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

        if cls.CONFIG_LOADED:
            print "Application already configured"
            return None
        
        print "Starting generic process service..."
        ps = ProcessService()
        print "Generic process service started\n"

        print "Trying to register current process"
        localId = ps.registerSelf()

        if( localId < 0 ):
            print "Failed to register current process - bailing out"
            return None

        cfg  = SimpleConfig( CommonConfig(), NodeConfig( localId ), cfgFile )

        cls.CONFIG_LOADED = True

        return AppConfig( cfg )

    ##############################
    def __init__( self, cfg ):
        self._cfg = cfg

    ##############################
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

    def getClientUuid( self ):
        return self._cfg.getNodeConfig().getClientUuid()

    def getGettingPeersInterval( self ):
        return self._cfg.getNodeConfig().getGettingPeersInterval()

    def getGettingTasksInterval( self ):
        return self._cfg.getNodeConfig().getGettingTasksInterval()

    def getTaskRequestInterval( self ):
        return self._cfg.getNodeConfig().getTaskRequestInterval()

    def getEstimatedPerformance( self ):
        return self._cfg.getNodeConfig().getEstimatedPerformance()

    def getNodeSnapshotInterval( self ):
        return self._cfg.getNodeConfig().getNodeSnapshotInterval()

    def getAddTasks( self ):
        return self._cfg.getNodeConfig().getAddTasks()

    def __str__( self ):
        return str( self._cfg )

if __name__ == "__main__":

    c = AppConfig( 0 )
    print c
    c = AppConfig( 1 )
    print c
    c = AppConfig( 2 )
    print c
