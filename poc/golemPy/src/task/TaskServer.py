
from network import Network
from TaskManager import TaskManager
from TaskComputer import TaskComputer
from TaskSession import TaskSession
from TaskBase import TaskHeader
from TaskConnState import TaskConnState
import random
import time
import cPickle

class TaskServer:
    #############################
    def __init__( self, address, configDesc ):

        self.configDesc         = configDesc

        self.address            = address
        self.curPort            = configDesc.startPort
        self.taskHeaders        = {}
        self.taskManager        = TaskManager( configDesc.clientUid )
        self.taskComputer       = TaskComputer( configDesc.clientUid, self, self.configDesc.estimatedPerformance, self.configDesc.taskRequestInterval )
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
    def requestTask( self, estimatedPerformance ):

        if len( self.taskHeaders.values() ) > 0:
            tn = random.randrange( 0, len( self.taskHeaders.values() ) )

            theader = self.taskHeaders.values()[ tn ]

            self.__connectAndSendTaskRequest( theader.taskOwnerAddress, theader.taskOwnerPort, theader.id, estimatedPerformance )

            return theader.id
        else:
            return 0

    #############################
    def requestResource( self, taskId, resourceHeader ):
        
        if taskId in self.taskHeaders:
            theader = self.taskHeaders[ taskId ]

            self.__connectAndSendResourceRequest( theader.taskOwnerAddress, theader.taskOwnerPort, theader.id, resourceHeader )
            return theader.id
        else:
            return 0

    #############################
    def sendResults( self, taskId, extraData, result ):
        
        if taskId in self.taskHeaders:
            theader = self.taskHeaders[ taskId ]
            if ( taskId, cPickle.dumps( extraData ) ) not in self.resultsToSend:
                self.resultsToSend[ ( taskId, cPickle.dumps( extraData ) ) ] = WaitingTaskResult( taskId, extraData, result, 0.0, 0.0 )
            else:
                assert False

            return True
        else:
            return False

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
            ret.append({    "id"            : th.id, 
                            "address"       : th.taskOwnerAddress,
                            "port"          : th.taskOwnerPort,
                            "ttl"           : th.ttl })

        return ret

    #############################
    def addTaskHeader( self, thDictRepr ):
        try:
            id = thDictRepr[ "id" ]
            if id not in self.taskHeaders.keys(): # dont have it
                if id not in self.taskManager.tasks.keys(): # It is not my task id
                    print "Adding task {}".format( id )
                    self.taskHeaders[ id ] = TaskHeader( id, thDictRepr[ "address" ], thDictRepr[ "port" ], thDictRepr[ "ttl" ] )
            return True
        except:
            print "Wrong task header received"
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
    def getWaitingTaskResult( self, taskId, extraData ):
        if ( taskId, cPickle.dumps( extraData ) ) in self.resultsToSend:
            return self.resultsToSend[ ( taskId, cPickle.dumps( extraData ) ) ]
        else:
            return None

    #############################
    def taskResultSent( self, taskId, extraData ):
        if ( taskId, cPickle.dumps( extraData ) ) in self.resultsToSend:
            del self.resultsToSend[ ( taskId, cPickle.dumps( extraData ) ) ]
        else:
            assert False

    #############################
    # PRIVATE SECTION

    #############################
    def __startAccepting(self):
        print "Enabling tasks accepting state"
        Network.listen( self.configDesc.startPort, self.configDesc.endPort, TaskServerFactory( self ), None, self.__listeningEstablished, self.__listeningFailure  )

    #############################
    def __listeningEstablished( self, port ):
        self.curPort = port
        print "Port {} opened - listening".format( port )
        self.taskManager.listenAddress = self.address
        self.taskManager.listenPort = self.curPort

    #############################
    def __listeningFailure(self, p):
        print "Opening {} port for listening failed, trying the next one".format( self.curPort )

        self.curPort = self.curPort + 1

        if self.curPort <= self.configDesc.endPort:
            self.__runListenOnce()
        else:
            #FIXME: some graceful terminations should take place here
            sys.exit(0)

    #############################   
    def __connectAndSendTaskRequest( self, address, port, taskId, estimatedPerformance ):    
        Network.connect( address, port, TaskSession, self.__connectionForTaskRequestEstablished, self.__connectionForTaskRequestFailure, taskId, estimatedPerformance )

    #############################   
    def __connectAndSendResourceRequest( self, address ,port, taskId, resourceHeader ):
        Network.connect( address, port, TaskSession, self.__connectionForResourceRequestEstablished, self.__connectionForResourceRequestFailure, taskId, resourceHeader )


    #############################
    def __connectionForTaskRequestEstablished( self, session, taskId, estimatedPerformance ):

        session.taskServer = self
        session.taskComputer = self.taskComputer
        session.taskManager = self.taskManager
        self.taskSeesions[ taskId ] = session            
        session.requestTask( taskId, estimatedPerformance )

    #############################
    def __connectionForTaskRequestFailure( self, session, taskId, estimatedPerformance ):
        print "Cannot connect to task {} owner".format( taskId )
        print "Removing task {} from task list".format( taskId )
        
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

        self.taskSeesions[ waitingTaskResult.taskId ] = session
        
        session.sendReportComputedTask( waitingTaskResult.taskId, waitingTaskResult.extraData )

    #############################
    def __connectionForTaskResultFailure( self, waitingTaskResult ):
        print "Cannot connect to task {} owner".format( waitingTaskResult.taskId )
        print "Removing task {} from task list".format( waitingTaskResult.taskId )
        
        waitingTaskResult.lastSendingTrial  = time.time()
        waitingTaskResult.delayTime         = self.configDesc.maxResultsSendignDelay
        waitingTaskResult.alreadySending    = False

    #############################
    def __connectionForResourceRequestEstablished( self, session, taskId, resourceHeader ):

        session.taskServer = self
        session.taskComputer = self.taskComputer
        session.taskManager = self.taskManager
        self.taskSeesions[ taskId ] = session            
        session.requestResource( taskId, resourceHeader )

    #############################
    def __connectionForResourceRequestFailure( self, session, taskId, resourceHeader ):
        print "Cannot connect to task {} owner".format( taskId )
        print "Removing task {} from task list".format( taskId )
        
        self.taskComputer.resourceRequestRejected( taskId, "Connection failed" )
        
        self.removeTaskHeader( taskId )
         
    #############################
    def __removeOldTasks( self ):
        for t in self.taskHeaders.values():
            currTime = time.time()
            t.ttl = t.ttl - ( currTime - t.lastChecking )
            t.lastChecking = currTime
            if t.ttl <= 0:
                print "Task {} dies".format( t.id )
                self.removeTaskHeader( t.id )

        self.taskManager.removeOldTasks()

    def __sendWaitingResults( self ):
        for wtr in self.resultsToSend:
            waitingTaskResult = self.resultsToSend[ wtr ]

            if not waitingTaskResult.alreadySending:
                if time.time() - waitingTaskResult.lastSendingTrial > waitingTaskResult.delayTime:
                    taskId = waitingTaskResult.taskId

                    if taskId in self.taskHeaders:
                        theader = self.taskHeaders[ taskId ]
                        waitingTaskResult.alreadySending = True
                        self.__connectAndSendTaskResults( theader.taskOwnerAddress, theader.taskOwnerPort, waitingTaskResult )

class WaitingTaskResult:
    #############################
    def __init__( self, taskId, extraData, result, lastSendingTrial, delayTime ):
        self.taskId             = taskId
        self.extraData          = extraData
        self.result             = result
        self.lastSendingTrial   = lastSendingTrial
        self.delayTime          = delayTime
        self.alreadySending     = False

from twisted.internet.protocol import Factory
from TaskConnState import TaskConnState

class TaskServerFactory(Factory):
    #############################
    def __init__( self, server ):
        self.server = server

    #############################
    def buildProtocol(self, addr):
        print "Protocol build for {}".format( addr )
        return TaskConnState( self.server )