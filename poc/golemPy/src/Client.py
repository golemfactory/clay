from twisted.internet import task, reactor

from P2PService import P2PService
from TaskServer import TaskServer

from TaskBase import TaskHeader
from ExampleTasks import VRayTracingTask

from hostaddress import getHostAddress

from NodeStateSnapshot import NodeStateSnapshot
from Message import MessagePeerStatus
from NodesManagerCient import NodesManagerClient

import sys
import time
import random
import socket

class Client:

    ############################
    def __init__(self, configDesc ):

        self.configDesc     = configDesc

        self.lastPingTime   = 0.0
        self.p2service      = None
        self.taskServer     = None
        self.lastPingTime   = time.time()
        self.lastNSSTime    = time.time()

        self.lastNodeStateSnapshot = None

        self.hostAddress    = getHostAddress()

        self.nodesManagerClient = None

        self.doWorkTask     = task.LoopingCall(self.__doWork)
        self.doWorkTask.start(0.1, False)
       
    ############################
    def startNetwork(self ):
        print "Starting network ..."
        print "Starting p2p server ..."
        self.p2pservice = P2PService( self.hostAddress, self.configDesc )

        time.sleep( 1.0 )

        print "Starting task server ..."
        self.taskServer = TaskServer( self.hostAddress, self.configDesc )

        self.p2pservice.setTaskServer( self.taskServer )

        time.sleep( 0.5 )

        print "Starting nodes manager client ..."
        self.nodesManagerClient = NodesManagerClient( self.configDesc.clientUuid, "127.0.0.1", self.configDesc.managerPort, self.taskServer.taskManager )
        self.nodesManagerClient.start()

        #self.taskServer.taskManager.addNewTask( )

    ############################
    def stopNetwork(self):
        #FIXME: Pewnie cos tu trzeba jeszcze dodac. Zamykanie serwera i wysylanie DisconnectPackege
        self.p2pservice         = None
        self.taskServer         = None
        self.nodesManagerClient = None

    ############################
    def __doWork(self):
        if self.p2pservice:
            if self.configDesc.sendPings:
                self.p2pservice.pingPeers( self.pingsInterval )

            self.p2pservice.syncNetwork()
            self.taskServer.syncNetwork()

            if time.time() - self.lastNSSTime > self.configDesc.nodeSnapshotInterval:
                self.__makeNodeStateSnapshot()
                self.lastNSSTime = time.time()

                #self.managerServer.sendStateMessage( self.lastNodeStateSnapshot )

    ############################
    def __makeNodeStateSnapshot( self, isRunning = True ):

        peersNum            = len( self.p2pservice.peers )
        lastNetworkMessages = self.p2pservice.getLastMessages()

        if self.taskServer:
            tasksNum                = len( self.taskServer.taskHeaders )
            remoteTasksProgresses   = self.taskServer.taskComputer.getProgresses()
            localTasksProgresses    = self.taskServer.taskManager.getProgresses()
            lastTaskMessages        = self.taskServer.getLastMessages()
            self.lastNodeStateSnapshot = NodeStateSnapshot(     isRunning
                                                           ,    self.configDesc.clientUuid
                                                           ,    peersNum
                                                           ,    tasksNum
                                                           ,    self.p2pservice.hostAddress
                                                           ,    self.p2pservice.p2pServer.curPort
                                                           ,    lastNetworkMessages
                                                           ,    lastTaskMessages
                                                           ,    remoteTasksProgresses  
                                                           ,    localTasksProgresses )
        else:
            self.lastNodeStateSnapshot = NodeStateSnapshot( self.configDesc.clientUuid, peersNum )

        if self.nodesManagerClient:
            self.nodesManagerClient.sendClientStateSnapshot( self.lastNodeStateSnapshot )
