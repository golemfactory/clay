from network import Network
from taskmanager import TaskManager
from taskcomputer import TaskComputer
from tasksession import TaskSession
from taskbase import TaskHeader
from taskconnstate import TaskConnState
import random
import time

class TaskServer:
    #############################
    def __init__( self, address, configDesc ):

        self.configDesc         = configDesc

        self.address            = address
        self.curPort            = configDesc.startPort
        self.taskHeaders        = {}
        self.taskManager        = TaskManager()
        self.taskComputer       = TaskComputer( self, self.configDesc.estimatedPerformance, self.configDesc.taskRequestInterval )
        self.taskSeesions       = {}
        self.taskSeesionsIncoming = []

        self.lastMessages       = []

        self.__startAccepting()

    #############################
    def syncNetwork( self ):
        self.taskComputer.run()
        self.__removeOldTasks()

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
    def sendResults( self, taskId, extraData, results ):
        
        if taskId in self.taskHeaders:
            theader = self.taskHeaders[ taskId ]
            self.__connectAndSendTaskResults( theader.taskOwnerAddress, theader.taskOwnerPort, taskId, extraData, results )
            return True
        else:
            return False

    #############################
    def newConnection(self, session):

        session.taskServer = self
        session.taskServer.taskComputer = self.taskComputer
        session.taskServer.taskManager = self.taskManager

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
        print "Connecting to host {} : {}".format( address ,port )
        
        Network.connect( address, port, TaskSession, self.__connectionForTaskRequestEstablished, self.__connectionForTaskRequestFailure, taskId, estimatedPerformance )

    #############################
    def __connectionForTaskRequestEstablished( self, session, taskId, estimatedPerformance ):

        session.taskServer = self
        session.taskServer.taskComputer = self.taskComputer
        session.taskServer.taskManager = self.taskManager
        self.taskSeesions[ taskId ] = session            
        ts.askForTask( taskId, estimatedPerformance )

    #############################
    def __connectionForTaskRequestFailure( self, session, taskId, estimatedPerformance ):
        print "Cannot connect to task {} owner".format( taskId )
        print "Removing task {} from task list".format( taskId )
        
        self.taskComputer.taskRequestRejected( taskId, "Connection failed" )
        
        self.removeTaskHeader( taskId )

    #############################   
    def __connectAndSendTaskResults( self, address, port, taskId, extraData, results ):
        print "Connecting to host {} : {}".format( address ,port )
        
        Network.connect( address, port, TaskSession, self.__connectionForTaskResultEstablished, self.__connectionForTaskResultFailure, taskId, extraData, results )

    #############################
    def __connectionForTaskResultEstablished( self, session, taskId, extraData, results ):

        session.taskServer = self
        session.taskServer.taskComputer = self.taskComputer
        session.taskServer.taskManager = self.taskManager

        self.taskSeesions[ taskId ] = session
        
        ts.sendTaskResults( taskId, extraData, results )

        ts.dropped()

    #############################
    def __connectionForTaskResultFailure( self, taskId, extraData, results ):
        print "Cannot connect to task {} owner".format( taskId )
        print "Removing task {} from task list".format( taskId )
                
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


from twisted.internet.protocol import Factory
from taskconnstate import TaskConnState

class TaskServerFactory(Factory):
    #############################
    def __init__( self, server ):
        self.server = server

    #############################
    def buildProtocol(self, addr):
        print "Protocol build for {}".format( addr )
        return TaskConnState( self.server )