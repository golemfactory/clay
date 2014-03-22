import sys
import psutil
sys.path.append('../src/')

from client import Client
from twisted.internet import reactor
from appconfig import DefaultConfig

def main():
    
    cfg = DefaultConfig()

    assert isinstance( cfg, DefaultConfig )

    optNumPeers     = cfg.getOptimalNumberOfPeers()
    startPort       = cfg.getStartPort()
    endPort         = cfg.getEndPort()
    seedHost        = cfg.getSeedHost()
    seedHostPort    = cfg.getSeedHostPort()
    sendPings       = cfg.getSendPings()
    pingsInterval   = cfg.getPingsInterval()
    clientUuid      = cfg.getClientUuid()

    c = Client( clientUuid, optNumPeers, startPort, endPort, sendPings, pingsInterval ) 
    c.startNetwork( seedHost, seedHostPort )

    reactor.run()


main()
