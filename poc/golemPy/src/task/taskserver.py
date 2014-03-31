from twisted.internet import reactor
from twisted.internet.protocol import Factory
from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint, connectProtocol

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
    def newConnection(self, conn):
        pp = conn.transport.getPeer()
        print "newConnection {} {}".format(pp.host, pp.port)
        tSession = TaskSession(conn, self, pp.host, pp.port)
        conn.setTaskSession( tSession )
        self.taskSeesionsIncoming.append( tSession )

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
        self.__runListenOnce()

    #############################
    def __runListenOnce( self ):
        ep = TCP4ServerEndpoint( reactor, self.curPort )
        
        d = ep.listen( TaskServerFactory( self ) )
        
        d.addCallback( self.__listeningEstablished )
        d.addErrback( self.__listeningFailure )

    #############################
    def __listeningEstablished(self, p):
        assert p.getHost().port == self.curPort
        print "Port {} opened - listening".format(p.getHost().port)

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
        
        endpoint = TCP4ClientEndpoint( reactor, address, port )
        connection = TaskConnState( self );
        
        d = connectProtocol( endpoint, connection )
        
        d.addCallback( self.__connectionForTaskRequestEstablished, taskId, estimatedPerformance )
        d.addErrback( self.__connectionForTaskRequestFailure, taskId, estimatedPerformance )

    #############################
    def __connectionForTaskRequestEstablished( self, conn, taskId, estimatedPerformance ):
        pp = conn.transport.getPeer()
        
        print "new task connection established {} {}".format( pp.host, pp.port )
        
        ts = TaskSession( conn, self, pp.host, pp.port )
        
        conn.setTaskSession( ts )
        self.taskSeesions[ taskId ] = ts     
        
        ts.askForTask( taskId, estimatedPerformance )

    #############################
    def __connectionForTaskRequestFailure( self, conn, taskId, estimatedPerformance ):
        print "Cannot connect to task {} owner".format( taskId )
        print "Removing task {} from task list".format( taskId )
        
        self.taskComputer.taskRequestRejected( taskId, "Connection failed" )
        
        self.removeTaskHeader( taskId )

    #############################   
    def __connectAndSendTaskResults( self, address, port, taskId, extraData, results ):
        print "Connecting to host {} : {}".format( address ,port )
        
        endpoint = TCP4ClientEndpoint( reactor, address, port )
        connection = TaskConnState( self );
        
        d = connectProtocol( endpoint, connection )
        
        d.addCallback( self.__connectionForTaskResultEstablished, taskId, extraData, results )
        d.addErrback( self.__connectionForTaskResultFailure, taskId, extraData, results )

    #############################
    def __connectionForTaskResultEstablished( self, conn, taskId, extraData, results ):
        pp = conn.transport.getPeer()
        
        print "new task connection established {} {}".format( pp.host, pp.port )
        
        ts = TaskSession( conn, self, pp.host, pp.port )
        
        self.taskSeesions[ taskId ] = ts     
        
        ts.sendTaskResults( taskId, extraData, results )

        ts.dropped()

    #############################
    def __connectionForTaskResultFailure( self, conn, taskId, extraData, results ):
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

class TaskServerFactory(Factory):
    #############################
    def __init__(self, p2pserver):
        self.p2pserver = p2pserver

    #############################
    def buildProtocol(self, addr):
        print "Protocol build for {}".format(addr)
        return TaskConnState(self.p2pserver)