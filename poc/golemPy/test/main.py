
import sys
sys.path.append('../src/')
sys.path.append('../src/core')
sys.path.append('../src/vm')

from twisted.internet import reactor

from appconfig import AppConfig
from client import Client


def test():
    lis = u''' l0
    l1
    l2
    l3
    4l
    l5'''

    from io import StringIO

    strm = StringIO( lis )
    for i in strm:
        print i.strip( )

def main():
    
    test()
    return

    cfg = AppConfig.loadConfig()

    optNumPeers     = cfg.getOptimalPeerNum()
    startPort       = cfg.getStartPort()
    endPort         = cfg.getEndPort()
    seedHost        = cfg.getSeedHost()
    seedHostPort    = cfg.getSeedHostPort()
    sendPings       = cfg.getSendPings()
    pingsInterval   = cfg.getPingsInterval()
    clientUuid      = cfg.getClientUuid()

    print "Creating public client interface with uuid: {}".format( clientUuid )
    c = Client( clientUuid, optNumPeers, startPort, endPort, sendPings, pingsInterval ) 

    print "Starting all asynchronous services"
    c.startNetwork( seedHost, seedHostPort )

    reactor.run()


main()
