
import sys
sys.path.append('../src/')
sys.path.append('../src/core')
sys.path.append('../src/vm')
sys.path.append('../testtasks/minilight/src')

from twisted.internet import reactor

from appconfig import AppConfig
from client import Client


def main():

    cfg = AppConfig.loadConfig()

    optNumPeers     = cfg.getOptimalPeerNum()
    startPort       = cfg.getStartPort()
    endPort         = cfg.getEndPort()
    seedHost        = cfg.getSeedHost()
    seedHostPort    = cfg.getSeedHostPort()
    sendPings       = cfg.getSendPings()
    pingsInterval   = cfg.getPingsInterval()
    clientUuid      = cfg.getClientUuid()
    addTasks        = cfg.getAddTasks()

    print "Adding tasks {}".format( addTasks )
    print "Creating public client interface with uuid: {}".format( clientUuid )
    c = Client( clientUuid, optNumPeers, startPort, endPort, sendPings, pingsInterval, addTasks ) 

    print "Starting all asynchronous services"
    c.startNetwork( seedHost, seedHostPort )

    reactor.run()


main()
