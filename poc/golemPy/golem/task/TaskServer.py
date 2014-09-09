
from golem.core.network import Network
from TaskManager import TaskManager
from TaskComputer import TaskComputer
from TaskSession import TaskSession
from TaskBase import TaskHeader
import random
import time
import sys
import os
import logging

logger = logging.getLogger(__name__)

class TaskServer:
    #############################
    def __init__( self, address, configDesc ):

        self.configDesc         = configDesc

        self.address            = address
        self.curPort            = configDesc.startPort
        self.taskHeaders        = {}
        self.taskManager        = TaskManager( configDesc.clientUid, rootPath = self.__getTaskManagerRoot( configDesc ) )
        self.taskComputer       = TaskComputer( configDesc.clientUid,
                                                self,
                                                self.configDesc.estimatedPerformance,
                                                self.configDesc.taskRequestInterval,
                                                self.__getTaskComputerRoot( configDesc ),
                                                self.configDesc.maxResourceSize,
                                                self.configDesc.maxMemorySize,
                                                self.configDesc.numCores )
        self.taskSeesions       = {}
        self.taskSeesionsIncoming = []

        self.lastMessages       = []

        self.resultsToSend      = {}

        self.__startAccepting()

    #############################
    def syncNetwork( self ):
        self.taskComputer.run()
        self.__removeOldTasks()
        self.__sendWaitingResults()

    #############################
    # This method chooses random task from the network to compute on our machine
    def requestTask( self, estimatedPerformance, maxResourceSize, maxMemorySize, numCores ):

        if len( self.taskHeaders.values() ) > 0:
            tn = random.randrange( 0, len( self.taskHeaders.values() ) )

            theader = self.taskHeaders.values()[ tn ]

            self.__connectAndSendTaskRequest( self.configDesc.clientUid, theader.taskOwnerAddress, theader.taskOwnerPort, theader.taskId, estimatedPerformance, maxResourceSize, maxMemorySize, numCores )

            return theader.taskId
        else:
            return 0

    #############################
    def requestResource( self, subtaskId, resourceHeader, address, port ):
        self.__connectAndSendResourceRequest( address, port, subtaskId, resourceHeader )
        return subtaskId

    #############################
    def sendResults( self, subtaskId, result, ownerAddress, ownerPort ):
        
        if subtaskId not in self.resultsToSend:
            self.resultsToSend[ subtaskId ] = WaitingTaskResult( subtaskId, result, 0.0, 0.0, ownerAddress, ownerPort )
        else:
            assert False

        return True

    #############################
    def newConnection(self, session):

        session.taskServer = self
        session.taskComputer = self.taskComputer
        session.taskManager = self.taskManager

        self.taskSeesionsIncoming.append( session )

    #############################
    def getTasksHeaders( self ):
        ths =  self.taskHeaders.values() + self.taskManager.getTasksHeaders()

        ret = []

        for th in ths:
            ret.append({    "id"            : th.taskId, 
                            "address"       : th.taskOwnerAddress,
                            "port"          : th.taskOwnerPort,
                            "ttl"           : th.ttl,
                            "subtaskTimeout": th.subtaskTimeout,
                            "clientId"      : th.clientId })

        return ret

    #############################
    def addTaskHeader( self, thDictRepr ):
        try:
            id = thDictRepr[ "id" ]
            if id not in self.taskHeaders.keys(): # dont have it
                if id not in self.taskManager.tasks.keys(): # It is not my task id
                    logger.info( "Adding task {}".format( id ) )
                    self.taskHeaders[ id ] = TaskHeader( thDictRepr[ "clientId" ], id, thDictRepr[ "address" ], thDictRepr[ "port" ], thDictRepr[ "ttl" ], thDictRepr["subtaskTimeout"] )
            return True
        except:
            logger.error( "Wrong task header received" )
            return False

    #############################
    def removeTaskHeader( self, taskId ):
        if taskId in self.taskHeaders:
            del self.taskHeaders[ taskId ]

    #############################
    def removeTaskSession( self, taskSession ):
        for tsk in self.taskSeesions.keys():
            if self.taskSeesions[ tsk ] == taskSession:
                del self.taskSeesions[ tsk ]

    #############################
    def setLastMessage( self, type, t, msg, address, port ):
        if len( self.lastMessages ) >= 5:
            self.lastMessages = self.lastMessages[ -4: ]

        self.lastMessages.append( [ type, t, address, port, msg ] )

    #############################
    def getLastMessages( self ):
        return self.lastMessages

    #############################
    def getWaitingTaskResult( self, subtaskId ):
        if subtaskId in self.resultsToSend:
            return self.resultsToSend[ subtaskId ]
        else:
            return None

    #############################
    def taskResultSent( self, subtaskId ):
        if subtaskId in self.resultsToSend:
            del self.resultsToSend[ subtaskId ]
        else:
            assert False

    #############################
    def changeConfig( self, configDesc ):
        self.configDesc = configDesc
        self.taskManager.changeConfig( self.__getTaskManagerRoot( configDesc ) )
        self.taskComputer.changeConfig( configDesc, self.__getTaskComputerRoot( configDesc ) )

    ############################
    def changeTimeouts( self, taskId, fullTaskTimeout, subtaskTimeout, minSubtaskTime ):
        self.taskManager.changeTimeouts( taskId, fullTaskTimeout, subtaskTimeout, minSubtaskTime )


    #############################
    # PRIVATE SECTION

    #############################
    def __startAccepting(self):
        logger.info( "Enabling tasks accepting state" )
        Network.listen( self.configDesc.startPort, self.configDesc.endPort, TaskServerFactory( self ), None, self.__listeningEstablished, self.__listeningFailure  )

    #############################
    def __listeningEstablished( self, port ):
        self.curPort = port
        logger.info( "Port {} opened - listening".format( port ) )
        self.taskManager.listenAddress = self.address
        self.taskManager.listenPort = self.curPort

    #############################
    def __listeningFailure(self, p):
        logger.warning( "Opening {} port for listening failed, trying the next one".format( self.curPort ) )

        self.curPort = self.curPort + 1

        if self.curPort <= self.configDesc.endPort:
            self.__runListenOnce()
        else:
            #FIXME: some graceful terminations should take place here
            sys.exit(0)

    #############################   
    def __connectAndSendTaskRequest( self, clientId, address, port, taskId, estimatedPerformance, maxResourceSize, maxMemorySize, numCores ):
        Network.connect( address, port, TaskSession, self.__connectionForTaskRequestEstablished, self.__connectionForTaskRequestFailure, clientId, taskId, estimatedPerformance, maxResourceSize, maxMemorySize, numCores )

    #############################   
    def __connectAndSendResourceRequest( self, address ,port, subtaskId, resourceHeader ):
        Network.connect( address, port, TaskSession, self.__connectionForResourceRequestEstablished, self.__connectionForResourceRequestFailure, subtaskId, resourceHeader )


    #############################
    def __connectionForTaskRequestEstablished( self, session, clientId, taskId, estimatedPerformance, maxResourceSize, maxMemorySize, numCores ):

        session.taskServer = self
        session.taskComputer = self.taskComputer
        session.taskManager = self.taskManager
        self.taskSeesions[ taskId ] = session            
        session.requestTask( clientId, taskId, estimatedPerformance, maxResourceSize, maxMemorySize, numCores )

    #############################
    def __connectionForTaskRequestFailure( self, clientId, taskId, estimatedPerformance ):
        logger.warning( "Cannot connect to task {} owner".format( taskId ) )
        logger.warning( "Removing task {} from task list".format( taskId ) )
        
        self.taskComputer.taskRequestRejected( taskId, "Connection failed" )
        
        self.removeTaskHeader( taskId )

    #############################   
    def __connectAndSendTaskResults( self, address, port, waitingTaskResult ):
        Network.connect( address, port, TaskSession, self.__connectionForTaskResultEstablished, self.__connectionForTaskResultFailure, waitingTaskResult )

    #############################
    def __connectionForTaskResultEstablished( self, session, waitingTaskResult ):

        session.taskServer = self
        session.taskComputer = self.taskComputer
        session.taskManager = self.taskManager

        self.taskSeesions[ waitingTaskResult.subtaskId ] = session
        
        session.sendReportComputedTask( waitingTaskResult.subtaskId )

    #############################
    def __connectionForTaskResultFailure( self, waitingTaskResult ):
        logger.warning( "Cannot connect to task {} owner".format( waitingTaskResult.subtaskId ) )
        logger.warning( "Removing task {} from task list".format( waitingTaskResult.subtaskId ) )
        
        waitingTaskResult.lastSendingTrial  = time.time()
        waitingTaskResult.delayTime         = self.configDesc.maxResultsSendingDelay
        waitingTaskResult.alreadySending    = False

    #############################
    def __connectionForResourceRequestEstablished( self, session, subtaskId, resourceHeader ):

        session.taskServer = self
        session.taskComputer = self.taskComputer
        session.taskManager = self.taskManager
        self.taskSeesions[ subtaskId ] = session
        session.taskId = subtaskId
        session.requestResource( subtaskId, resourceHeader )

    #############################
    def __connectionForResourceRequestFailure( self, session, subtaskId, resourceHeader ):
        logger.warning( "Cannot connect to task {} owner".format( subtaskId ) )
        logger.warning( "Removing task {} from task list".format( subtaskId ) )
        
        self.taskComputer.resourceRequestRejected( subtaskId, "Connection failed" )
        
        self.removeTaskHeader( subtaskId )
         
    #############################
    def __removeOldTasks( self ):
        for t in self.taskHeaders.values():
            currTime = time.time()
            t.ttl = t.ttl - ( currTime - t.lastChecking )
            t.lastChecking = currTime
            if t.ttl <= 0:
                logger.warning( "Task {} dies".format( t.taskId ) )
                self.removeTaskHeader( t.taskId )

        self.taskManager.removeOldTasks()

    def __sendWaitingResults( self ):
        for wtr in self.resultsToSend:
            waitingTaskResult = self.resultsToSend[ wtr ]

            if not waitingTaskResult.alreadySending:
                if time.time() - waitingTaskResult.lastSendingTrial > waitingTaskResult.delayTime:
                    subtaskId = waitingTaskResult.subtaskId

                    waitingTaskResult.alreadySending = True
                    self.__connectAndSendTaskResults( waitingTaskResult.ownerAddress, waitingTaskResult.ownerPort, waitingTaskResult )

    def __getTaskManagerRoot( self, configDesc ):
        return os.path.join( configDesc.rootPath, "res" )

    def __getTaskComputerRoot( self, configDesc ):
        return os.path.join( configDesc.rootPath, "ComputerRes")

class WaitingTaskResult:
    #############################
    def __init__( self, subtaskId, result, lastSendingTrial, delayTime, ownerAddress, ownerPort  ):
        self.subtaskId          = subtaskId
        self.result             = result
        self.lastSendingTrial   = lastSendingTrial
        self.delayTime          = delayTime
        self.ownerAddress       = ownerAddress
        self.ownerPort          = ownerPort
        self.alreadySending     = False

from twisted.internet.protocol import Factory
from TaskConnState import TaskConnState

class TaskServerFactory(Factory):
    #############################
    def __init__( self, server ):
        self.server = server

    #############################
    def buildProtocol(self, addr):
        logger.info( "Protocol build for {}".format( addr ) )
        return TaskConnState( self.server )