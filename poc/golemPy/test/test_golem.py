import sys
sys.path.append('../src/')

from client import Client
from twisted.internet import reactor
from GolemConfig import DefaultConfig

def main():
    
    cfg = DefaultConfig()

    assert isinstance( cfg, DefaultConfig )

    optNumPeers     = cfg.getOptimalNumberOfPeers()
    startPort       = cfg.getStartPort()
    endPort         = cfg.getEndPort()
    seedHost        = cfg.getSeedHost()
    seedHostPort    = cfg.getSeedHostPort()

    c = Client( optNumPeers, startPort, endPort ) 
    c.startNetwork( seedHost, seedHostPort )

    reactor.run()


main()
