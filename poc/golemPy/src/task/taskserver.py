from taskmanager import TaskManager
from taskcomputer import TaskComputer
from tasksession import TaskSession
from task import TaskHeader
import random

class TaskServer:
    #############################
    def __init__( self, address, startPort, endPort, clientPerformance, taskRequestFrequency ):
        self.address            = address
        self.startPort          = startPort
        self.endPort            = endPort
        self.curPort            = startPort
        self.taskHeaders        = []
        self.taskManager        = TaskManager()
        self.taskComputer       = TaskComputer( self, clientPerformance, taskRequestFrequency )
        self.taskSeesions       = {}
        self.taskSeesionsIncoming = []

        self.__startAccepting()

    #############################
    # This method chooses random task from the network to compute on our machine
    def requestTask( self, estimatedPerformance ):

        tn = random.randrange( 0, len( self.taskHeaders ) )

        theader = tasks[ tn ].desc

        self.__connectAndSendTaskRequest( theader.taskOwnerAddress, theader.taskOwnerPort, theader.id, estimatedPerformance )

        return theader.id

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
        print "newComputeConnection {} {}".format(pp.host, pp.port)
        computeSession = TaskSession(conn, self, pp.host, pp.port)
        self.computeSessions[ [ pp.host, pp.port ] ] = computeSession

    #############################
    # PRIVATE SECSSION

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
        print "Opening {} port for listetning failed, trying the next one".format( self.curPort )

        self.curPort = self.curPort + 1

        if self.curPort <= self.endPort:
            self.__runListenOnceCompute()
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
        
        self.taskSeesions[ taskId ] = computeSession     
        
        ts.askForTask( taskId, estimatedPerformance )

    #############################
    def __connectionForTaskRequestFailure( self, conn, taskId, estimatedPerformance ):
        print "Cannot connect to task {} owner".format( taskId )
        print "Removing task {} from task list".format( taskId )
        
        self.taskComputer.taskRequestRejected( taskId, "Connection failed" )
        
        if taskId in self.taskHeaders:
            del self.taskHeaders[ taskId ]


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
        
        self.taskSeesions[ taskId ] = computeSession     
        
        ts.sendTaskResults( taskId, extraData, results )

        ts.dropped()

    #############################
    def __connectionForTaskResultFailure( self, conn, taskId, extraData, results ):
        print "Cannot connect to task {} owner".format( taskId )
        print "Removing task {} from task list".format( taskId )
                
        if taskId in self.taskHeaders:
            del self.taskHeaders[ taskId ]



class TaskServerFactory(Factory):
    #############################
    def __init__(self, p2pserver):
        self.p2pserver = p2pserver

    #############################
    def buildProtocol(self, addr):
        print "Protocol build for {}".format(addr)
        return TaskConnState(self.p2pserver)