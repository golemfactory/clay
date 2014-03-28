from twisted.internet import task
from twisted.internet import reactor

from p2pserver import P2PServer
from taskserver import TaskServer
from taskmanager import TaskManager
from taskcomputer import TaskComputer

import sys
import time

PING_INTERVAL = 1.0
TASK_REQUEST_FREQ = 1.0
ESTIMATED_PERFORMANCE = 1200.0

class Client:
    ############################
    def __init__(self, publicKey, optimalNumPeers, startPort, endPort, sendPings, pingsInterval, addTasks ):

        self.optNumPeers    = optimalNumPeers
        self.startPort      = startPort
        self.endPort        = endPort
        self.sendPings      = sendPings
        self.pingsInterval  = pingsInterval
        self.addTasks       = addTasks

        self.lastPingTime   = 0.0
        self.publicKey      = publicKey
        self.p2pserver      = None
        self.taskServer     = None 
        self.taskManager    = None
        self.taskComputer   = None
        self.lastPingTime   = time.time()

        self.doWorkTask     = task.LoopingCall(self.__doWork)
        self.doWorkTask.start(0.1, False)


    ############################
    def startNetwork(self, seedHost, seedHostPort):
        print "Starting network ..."
        self.p2pserver = P2PServer(1, self.startPort, self.endPort, self.publicKey, seedHost, seedHostPort)
        self.taskServer = TaskServer( "", self.startPort, self.endPort, ESTIMATED_PERFORMANCE, TASK_REQUEST_FREQ )
        if self.addTasks:
            self.taskServer.taskManager.addNewTask( None )

    ############################
    def stopNetwork(self):
        #FIXME: Pewnie cos tu trzeba jeszcze dodac. Zamykanie serwera i wysylanie DisconnectPackege
        self.p2pserver = None

    ############################
    def __doWork(self):
        if self.p2pserver:
            if self.sendPings:
                self.p2pserver.pingPeers( self.pingsInterval )

            self.p2pserver.syncNetwork()
            self.p2pserver.taskManager.runTasks()
            