from twisted.internet import task
from twisted.internet import reactor

from p2pserver import P2PServer

import sys
import time

PING_INTERVAL = 1.0

class Client:
    ############################
    def __init__(self, publicKey, optimalNumPeers, startPort, endPort, sendPings, pingsInterval ):

        self.optNumPeers    = optimalNumPeers
        self.startPort      = startPort
        self.endPort        = endPort
        self.sendPings      = sendPings
        self.pingsInterval  = pingsInterval

        self.lastPingTime = 0.0
        self.publicKey = publicKey
        self.p2pserver = None

        self.doWorkTask = task.LoopingCall(self.__doWork)
        self.doWorkTask.start(0.1, False)
        self.lastPingTime = time.time()

    ############################
    def startNetwork(self, seedHost, seedHostPort):
        print "Starting network ..."
        self.p2pserver = P2PServer(1, self.startPort, self.endPort, self.publicKey, seedHost, seedHostPort)

    ############################
    def stopNetwork(self):
        #FIXME: Pewnie cos tu trzeba jeszcze dodac. Zamykanie serwera i wysylanie DisconnectPackege
        self.p2pserver = None

    ############################
    #def connect(self, address, port):
    #    if self.p2pserver:
    #        self.p2pserver.connectNet(address, port)
    #    else:
    #        print "Trying to connect when server is not started yet"

    ############################
    def __doWork(self):
        if self.p2pserver:
            if self.sendPings:
                self.p2pserver.pingPeers( self.pingsInterval )

            self.p2pserver.syncNetwork()
            self.p2pserver.taskManager.runTasks()
            