import ConfigParser
import os
import shutil
import uuid

GOLEM_CFG_INI_FILENAME = "golem_test_config.ini"

class DefaultConfig:

    MAIN_SECTION_STR        = "GOLEM CONFIG"
    #DEFAULT_NODE_TYPE

    DEFAULT_OPTIMAL_PEER_NUM    = 10
    DEFAULT_START_PORT          = 40102
    DEFAULT_END_PORT            = 60102
    DEFAULT_SEED_HOST           = ""
    DEFAULT_SEED_HOST_PORT      = 0
    DEFAULT_SEND_PINGS          = 0
    DEFAULT_PINGS_INTERVAL      = 0.0
    DEFAULT_UUID                = u""

    OPTIMAL_PEER_NUM_STR    = "optimal peer num"
    START_PORT_STR          = "start port"
    END_PORT_STR            = "end port"
    SEED_HOST_STR           = "seed host"
    SEED_HOST_PORT_STR      = "seed host port"
    SEND_PINGS_STR          = "send pings"
    PINGS_INTERVAL_STR      = "pigns interval"
    UUID_STR                = "client clientUuid"

    def __init__(self, iniFile = GOLEM_CFG_INI_FILENAME):
        
        self.optimalPeerNum = DefaultConfig.DEFAULT_OPTIMAL_PEER_NUM
        self.startPort      = DefaultConfig.DEFAULT_START_PORT
        self.endPort        = DefaultConfig.DEFAULT_END_PORT
        self.seedHost       = DefaultConfig.DEFAULT_SEED_HOST
        self.seedHostPort   = DefaultConfig.DEFAULT_SEED_HOST_PORT
        self.sendPings      = DefaultConfig.DEFAULT_SEND_PINGS
        self.pingsInterval  = DefaultConfig.DEFAULT_PINGS_INTERVAL
        self.clientUuid     = DefaultConfig.DEFAULT_UUID

        print "Reading config from file {}".format( iniFile ), 

        try:
            cfg = ConfigParser.ConfigParser()
            cfg.read( iniFile )
            
            optimalPeerNum  = int( cfg.get( DefaultConfig.MAIN_SECTION_STR, DefaultConfig.OPTIMAL_PEER_NUM_STR ) )
            startPort       = int( cfg.get( DefaultConfig.MAIN_SECTION_STR, DefaultConfig.START_PORT_STR ) )
            endPort         = int( cfg.get( DefaultConfig.MAIN_SECTION_STR, DefaultConfig.END_PORT_STR ) )
            seedHost        = cfg.get( DefaultConfig.MAIN_SECTION_STR, DefaultConfig.SEED_HOST_STR )
            seedHostPort    = int( cfg.get( DefaultConfig.MAIN_SECTION_STR, DefaultConfig.SEED_HOST_PORT_STR ) )
            sendPings       = int( cfg.get( DefaultConfig.MAIN_SECTION_STR, DefaultConfig.SEND_PINGS_STR ) )
            pingsInterval   = float( cfg.get( DefaultConfig.MAIN_SECTION_STR, DefaultConfig.PINGS_INTERVAL_STR ) )
            clientUuid      = cfg.get( DefaultConfig.MAIN_SECTION_STR, DefaultConfig.UUID_STR )

            if len( clientUuid ) == 0:
                clientUuid = uuid.uuid1().get_hex()

            self.optimalPeerNum = optimalPeerNum 
            self.startPort      = startPort      
            self.endPort        = endPort        
            self.seedHost       = seedHost       
            self.seedHostPort   = seedHostPort
            self.sendPings      = sendPings
            self.pingsInterval  = pingsInterval
            self.clientUuid     = clientUuid

            print " ... successfully"

        except Exception as ex:
            print " ... failed with exception {}".format( ex )
            print "Trying to write default values to config file (keeping old data in bak file)"

            if os.path.isfile( iniFile ):
                shutil.copy( iniFile, iniFile + ".bak" )

            cfgfile = open( iniFile, 'w' ) #no try catch because this cannot fail (if it fails then the program shouldn't start anyway)
          
            cfg = ConfigParser.ConfigParser()

            cfg.add_section( DefaultConfig.MAIN_SECTION_STR )

            cfg.set( DefaultConfig.MAIN_SECTION_STR, DefaultConfig.OPTIMAL_PEER_NUM_STR, self.optimalPeerNum )
            cfg.set( DefaultConfig.MAIN_SECTION_STR, DefaultConfig.START_PORT_STR, self.startPort )
            cfg.set( DefaultConfig.MAIN_SECTION_STR, DefaultConfig.END_PORT_STR, self.endPort )
            cfg.set( DefaultConfig.MAIN_SECTION_STR, DefaultConfig.SEED_HOST_STR, self.seedHost )
            cfg.set( DefaultConfig.MAIN_SECTION_STR, DefaultConfig.SEED_HOST_PORT_STR, self.seedHostPort )
            cfg.set( DefaultConfig.MAIN_SECTION_STR, DefaultConfig.SEND_PINGS_STR, self.sendPings )
            cfg.set( DefaultConfig.MAIN_SECTION_STR, DefaultConfig.PINGS_INTERVAL_STR, self.pingsInterval )
            cfg.set( DefaultConfig.MAIN_SECTION_STR, DefaultConfig.UUID_STR, uuid.uuid1().get_hex() )

            cfg.write( cfgfile )
            
            cfgfile.close()
    
    def getOptimalNumberOfPeers( self ):
        return self.optimalPeerNum

    def getStartPort( self ):
        return self.startPort

    def getEndPort( self ):
        return self.endPort

    def getSeedHost( self ):
        return self.seedHost

    def getSeedHostPort( self ):
        return self.seedHostPort

    def getSendPings( self ):
        return self.sendPings

    def getPingsInterval( self ):
        return self.pingsInterval

    def getClientUuid( self ):
        return self.clientUuid


    def __str__( self ):
        rs = "DefaultConfig\n"
        rs += "{:20} {self.optimalPeerNum}\n".format( "optimalPeerNumb", self = self )
        rs += "{:20} {self.startPort}\n".format( "startPort", self = self )
        rs += "{:20} {self.endPort}\n".format( "endPort", self = self )
        rs += "{:20} {self.seedHost}\n".format( "seedHost", self = self )
        rs += "{:20} {self.seedHostPort}\n".format( "seedHostPort", self = self )
        rs += "{:20} {self.sendPings}\n".format( "sendPings", self = self )
        rs += "{:20} {self.pingsInterval}".format( "pingsInterval", self = self )
        rs += "{:20} {self.clientUuid}".format( "clientUuid", self = self )

        return rs

if __name__ == "__main__":

    cfg = DefaultConfig()
    print cfg
