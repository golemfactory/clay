import sys
sys.path.append('core')

from simpleconfig import SimpleConfig, ConfigEntry
from prochelper import ProcessService

CONFIG_FILENAME = "app_cfg.ini"

class CommonConfig:

    ##############################
    def __init__( self, section = "Common" ):

        self._section = section

        ConfigEntry.createProperty( section, "optimal peer num",    10,    self, "OptimalPeerNum" )
        ConfigEntry.createProperty( section, "start port",          40102, self, "StartPort" )
        ConfigEntry.createProperty( section, "end port",            60102, self, "EndPort" )

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
        ConfigEntry.createProperty( self.section(), "compute listen port", 30456, self, "computeListenPort" )
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

    def getComputeListenPort( self ):
        return self._cfg.getNodeConfig().getComputeListenPort()

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
