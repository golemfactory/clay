import sys
sys.path.append('core')

from simpleconfig import SimpleConfig, ConfigEntry

CONFIG_FILENAME = "app_cfg.ini"

class CommonConfig:

    ##############################
    def __init__( self, section = "Common" ):

        self._section = section

        ConfigEntry.createProperty( section, "optimal peer num", 10,    self, "OptimalPeerNum" )
        ConfigEntry.createProperty( section, "start port",       40102, self, "StartPort" )
        ConfigEntry.createProperty( section, "end port",         60102, self, "EndPort" )

    ##############################
    def section( self ):
        return self._section


class NodeConfig:

    ##############################
    def __init__( self, nodeId ):
        self._section = "Node {}".format( nodeId )

        ConfigEntry.createProperty( self.section(), "seed host",        "",   self, "SeedHost" )
        ConfigEntry.createProperty( self.section(), "seed host port",    0,   self, "SeedHostPort")
        ConfigEntry.createProperty( self.section(), "send pings",        0,   self, "SendPings" )
        ConfigEntry.createProperty( self.section(), "pigns interval",    0,   self, "PingsInterval" )
        ConfigEntry.createProperty( self.section(), "client clientUuid", u"", self, "ClientUuid" )

    ##############################
    def section( self ):
        return self._section


##############################
##############################
class AppConfig:

    ##############################
    def __init__(self, localId, iniFile = CONFIG_FILENAME):

        cCfg = CommonConfig()
        nCfg = NodeConfig( localId )

        self._cfg = SimpleConfig( cCfg, nCfg, iniFile )
    

    def getOptimalPeerNum( self ):
        return self._cfg.getComonConfig().getOptimalPeerNum()

    def getStartPort( self ):
        return self._cfg.getComonConfig().getStartPort()

    def getEndPort( self ):
        return self._cfg.getComonConfig().getEndPort()

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

    def __str__( self ):
        return str( self._cfg )

if __name__ == "__main__":

    c = AppConfig( 0 )
    print c
    c = AppConfig( 1 )
    print c
    c = AppConfig( 2 )
    print c
