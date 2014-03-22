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

    optNumPeers     = cfg.getOptimalNumberOfPeers()
    startPort       = cfg.getStartPort()
    endPort         = cfg.getEndPort()
    seedHost        = cfg.getSeedHost()
    seedHostPort    = cfg.getSeedHostPort()
    sendPings       = cfg.getSendPings()
    pingsInterval   = cfg.getPingsInterval()
    clientUuid      = cfg.getClientUuid()

    print "Creating public client interface uuid: {}".format( clientUuid )
    c = Client( clientUuid, optNumPeers, startPort, endPort, sendPings, pingsInterval ) 

    print "Starting all asynchronous services"
    c.startNetwork( seedHost, seedHostPort )

    reactor.run()


main()
