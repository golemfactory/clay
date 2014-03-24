import sys
sys.path.append('../src/')
sys.path.append('../src/core')

from prochelper import ProcessService
from appconfig import DefaultConfig
from client import Client
from twisted.internet import reactor

def main():
    
    print "Starting generic process service..."
    ps = ProcessService()
    print "Generic process service started\n"

    print "Trying to register current process"
    localId = ps.registerSelf()

    if( localId < 0 ):
        print "Failed to register current process - bailing out"
        return

    print "Process registered successfully with local id {}\n".format( localId )

    print "Trying to acquire node config"
    cfg = DefaultConfig( localId )
    print "Configuration read successfully\n"

    assert isinstance( cfg, DefaultConfig )

    gCfg = cfg.getCommonConfig()
    nCfg = cfg.getNodeConfig()

    optNumPeers     = gCfg.getOptimalPeerNum()
    startPort       = gCfg.getStartPort()
    endPort         = gCfg.getEndPort()
    seedHost        = nCfg.getSeedHost()
    seedHostPort    = nCfg.getSeedHostPort()
    sendPings       = nCfg.getSendPings()
    pingsInterval   = nCfg.getPingsInterval()
    clientUuid      = nCfg.getClientUuid()

    print "Creating public client interface with uuid: {}".format( clientUuid )
    c = Client( clientUuid, optNumPeers, startPort, endPort, sendPings, pingsInterval ) 

    print "Starting all asynchronous services"
    c.startNetwork( seedHost, seedHostPort )

    reactor.run()


main()
