from twisted.internet import task

from p2pserver import P2PServer
from taskserver import TaskServer

from taskbase import TaskHeader
from exampletasks import VRayTracingTask

import sys
import time
import random

TASK_REQUEST_FREQ = 5.0
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
        self.lastPingTime   = time.time()

        self.doWorkTask     = task.LoopingCall(self.__doWork)
        self.doWorkTask.start(0.1, False)


    ############################
    def startNetwork(self, seedHost, seedHostPort):
        print "Starting network ..."
        self.p2pserver = P2PServer(1, self.startPort, self.endPort, self.publicKey, seedHost, seedHostPort)

        time.sleep( 2.0 )

        self.taskServer = TaskServer( "", self.startPort, self.endPort, ESTIMATED_PERFORMANCE, TASK_REQUEST_FREQ )
        if self.addTasks:
            hash = random.getrandbits(128)
            th = TaskHeader( hash, "10.30.10.203", self.taskServer.curPort )
            self.taskServer.taskManager.addNewTask( VRayTracingTask( 10, 10, 10, th ) )

        self.p2pserver.setTaskServer( self.taskServer )

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
            self.taskServer.syncNetwork()