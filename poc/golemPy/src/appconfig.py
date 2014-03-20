import ConfigParser
import os
import shutil
import uuid

GOLEM_CFG_INI_FILENAME = "golem_test_config.ini"

class ConfigEntry:

    def __init__( self, key, value ):
        self._key = key
        self._value = value

    def key( self ):
        return self._key

    def value( self ):
        return self._value

    def setKey( self, k ):
        self._key = k

    def setValue( self, v ):
        self._value = v

class DefaultConfig:


    MAIN_SECTION_STR        = "GOLEM CONFIG"
    #DEFAULT_NODE_TYPE

    def __init__(self, iniFile = GOLEM_CFG_INI_FILENAME):
        
        self.optimalPeerNum = ConfigEntry( "optimal peer num",  10 )
        self.startPort      = ConfigEntry( "start port",        40102 )
        self.endPort        = ConfigEntry( "end port",          60102 )
        self.seedHost       = ConfigEntry( "seed host",         "" )
        self.seedHostPort   = ConfigEntry( "seed host port",    0 )
        self.sendPings      = ConfigEntry( "send pings",        0 )
        self.pingsInterval  = ConfigEntry( "pigns interval",    0 )
        self.clientUuid     = ConfigEntry( "client clientUuid", u"" )

        print "Reading config from file {}".format( iniFile ), 

        try:
            cfg = ConfigParser.ConfigParser()

            cfg.read( iniFile )
            
            self.optimalPeerNum.setValue    ( int(   self.__readOption( cfg, self.optimalPeerNum ) ) )
            self.startPort.setValue         ( int(   self.__readOption( cfg, self.startPort ) ) )
            self.endPort.setValue           ( int(   self.__readOption( cfg, self.endPort ) ) )
            self.seedHost.setValue          (        self.__readOption( cfg, self.seedHost ) )
            self.seedHostPort.setValue      ( int(   self.__readOption( cfg, self.seedHostPort ) ) )
            self.sendPings.setValue         ( int (  self.__readOption( cfg, self.sendPings ) ) )
            self.pingsInterval.setValue     ( float( self.__readOption( cfg, self.pingsInterval ) ) )
            self.clientUuid.setValue        (        self.__readOption( cfg, self.clientUuid ) )
                                                          
            if len( self.clientUuid.value() ) == 0:
                self.clientUuid.setValue( uuid.uuid1().get_hex() )

            print " ... successfully"

        except Exception as ex:
            print " ... failed with exception {}".format( ex )
            print "Trying to write default values to config file (keeping old data in bak file)"

            if len( self.clientUuid.value() ) == 0:
                self.clientUuid.setValue( uuid.uuid1().get_hex() )

            if os.path.isfile( iniFile ):
                shutil.copy( iniFile, iniFile + ".bak" )

            cfgfile = open( iniFile, 'w' ) #no try catch because this cannot fail (if it fails then the program shouldn't start anyway)
          
            cfg = ConfigParser.ConfigParser()

            cfg.add_section( DefaultConfig.MAIN_SECTION_STR )

            self.__writeOption( cfg, self.optimalPeerNum )
            self.__writeOption( cfg, self.startPort )
            self.__writeOption( cfg, self.endPort )
            self.__writeOption( cfg, self.seedHost )
            self.__writeOption( cfg, self.seedHostPort )
            self.__writeOption( cfg, self.sendPings )
            self.__writeOption( cfg, self.pingsInterval )
            self.__writeOption( cfg, self.clientUuid )

            cfg.write( cfgfile )
            
            cfgfile.close()
    
    def getOptimalNumberOfPeers( self ):
        return self.optimalPeerNum.value()

    def getStartPort( self ):
        return self.startPort.value()

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

    def __readOption( self, cfg, cfgOption ):
        return cfg.get( DefaultConfig.MAIN_SECTION_STR, cfgOption.key() )

    def __writeOption( self, cfg, cfgOption ):
        return cfg.set( DefaultConfig.MAIN_SECTION_STR, cfgOption.key(), cfgOption.value() )

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
