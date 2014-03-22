import ConfigParser
import os
import shutil
import uuid

GOLEM_CFG_INI_FILENAME = "test_config.ini"

##############################
class ConfigEntry:

    def __init__( self, section, key, value ):
        self._key = key
        self._value = value
        self._section = section

    def section( self ):
        return self._section

    def key( self ):
        return self._key

    def value( self ):
        return self._value

    def setKey( self, k ):
        self._key = k

    def setValue( self, v ):
        self._value = v

##############################
class DefaultConfig:

    MAIN_SECTION_STR        = "GOLEM CONFIG"
    ENTRY_STR               = "NODE_ENTRY_"
    #DEFAULT_NODE_TYPE

    ##############################
    def __init__(self, localId, iniFile = GOLEM_CFG_INI_FILENAME):

        entrySection = "{}{}".format( DefaultConfig.ENTRY_STR, localId )

        self.optimalPeerNum = ConfigEntry( DefaultConfig.MAIN_SECTION_STR, "optimal peer num",  10 )
        self.startPort      = ConfigEntry( DefaultConfig.MAIN_SECTION_STR, "start port",        40102 )
        self.endPort        = ConfigEntry( DefaultConfig.MAIN_SECTION_STR, "end port",          60102 )
        self.seedHost       = ConfigEntry( entrySection, "seed host",         "" )
        self.seedHostPort   = ConfigEntry( entrySection, "seed host port",    0 )
        self.sendPings      = ConfigEntry( entrySection, "send pings",        0 )
        self.pingsInterval  = ConfigEntry( entrySection, "pigns interval",    0 )
        self.clientUuid     = ConfigEntry( entrySection, "client clientUuid", u"" )

        print "Reading config from file {}".format( iniFile ), 

        writeConfig = False
        cfg = ConfigParser.ConfigParser()
        files = cfg.read( iniFile )

        if len( files ) == 1:
            if entrySection in cfg.sections():
                assert DefaultConfig.MAIN_SECTION_STR in cfg.sections()

                self.__readOptions( cfg )

                if len( self.clientUuid.value() ) == 0:
                    writeConfig = True
            else:
                cfg.add_section( entrySection )
                writeConfig = True

            print " ... successfully"
        else:
            cfg = self.__createFreshConfig( entrySection )
            writeConfig = True

        if writeConfig:
            print "Writing confing for current entry {} to config file {}".format( entrySection, iniFile )

            print "Generating fresh UUID for current node"
            self.clientUuid.setValue( uuid.uuid1().get_hex() )

            self.__writeOptions( cfg )
   
            cfgfile = open( iniFile, 'w' ) #no try catch because this cannot fail (if it fails then the program shouldn't start anyway)
            cfg.write( cfgfile )            
            cfgfile.close()
    
    ##############################
    def getOptimalNumberOfPeers( self ):
        return self.optimalPeerNum.value()

    ##############################
    def getStartPort( self ):
        return self.startPort.value()

    ##############################
    def getEndPort( self ):
        return self.endPort.value()

    ##############################
    def getSeedHost( self ):
        return self.seedHost.value()

    ##############################
    def getSeedHostPort( self ):
        return self.seedHostPort.value()

    ##############################
    def getSendPings( self ):
        return self.sendPings.value()

    ##############################
    def getPingsInterval( self ):
        return self.pingsInterval.value()

    ##############################
    def getClientUuid( self ):
        return self.clientUuid.value()

    ##############################
    def __createFreshConfig( self, entrySection ):
        cfg = ConfigParser.ConfigParser()
        cfg.add_section( DefaultConfig.MAIN_SECTION_STR )
        cfg.add_section( entrySection )

        return cfg

    ##############################
    def __readOption( self, cfg, cfgOption ):
        return cfg.get( cfgOption.section(), cfgOption.key() )

    ##############################
    def __writeOption( self, cfg, cfgOption ):
        return cfg.set( cfgOption.section(), cfgOption.key(), cfgOption.value() )

    ##############################
    def __readOptions( self, cfg ):

        self.optimalPeerNum.setValue    ( int(   self.__readOption( cfg, self.optimalPeerNum ) ) )
        self.startPort.setValue         ( int(   self.__readOption( cfg, self.startPort ) ) )
        self.endPort.setValue           ( int(   self.__readOption( cfg, self.endPort ) ) )
        self.seedHost.setValue          (        self.__readOption( cfg, self.seedHost ) )
        self.seedHostPort.setValue      ( int(   self.__readOption( cfg, self.seedHostPort ) ) )
        self.sendPings.setValue         ( int (  self.__readOption( cfg, self.sendPings ) ) )
        self.pingsInterval.setValue     ( float( self.__readOption( cfg, self.pingsInterval ) ) )
        self.clientUuid.setValue        (        self.__readOption( cfg, self.clientUuid ) )

    ##############################
    def __writeOptions( self, cfg ):

        self.__writeOption( cfg, self.optimalPeerNum )
        self.__writeOption( cfg, self.startPort )
        self.__writeOption( cfg, self.endPort )
        self.__writeOption( cfg, self.seedHost )
        self.__writeOption( cfg, self.seedHostPort )
        self.__writeOption( cfg, self.sendPings )
        self.__writeOption( cfg, self.pingsInterval )
        self.__writeOption( cfg, self.clientUuid )

    ##############################
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

    cfg = DefaultConfig( 0, "some_test_cfg.ini" )
    cfg1 = DefaultConfig( 1, "some_test_cfg.ini" )
    cfg2 = DefaultConfig( 2, "some_test_cfg.ini" )
