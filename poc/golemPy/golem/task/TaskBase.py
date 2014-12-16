import time
import abc

class TaskHeader:
    #######################
    def __init__( self, clientId, taskId, taskOwnerAddress, taskOwnerPort, environment, ttl = 0.0, subtaskTimeout = 0.0, resourceSize = 0, estimatedMemory = 0, minVersion = 1.0 ):
        self.taskId = taskId
        self.taskOwnerAddress = taskOwnerAddress
        self.taskOwnerPort = taskOwnerPort
        self.lastChecking = time.time()
        self.ttl = ttl
        self.subtaskTimeout = subtaskTimeout
        self.clientId = clientId
        self.resourceSize = resourceSize
        self.environment = environment
        self.estimatedMemory = estimatedMemory
        self.minVersion = minVersion

class TaskBuilder:
    #######################
    def __init__( self ):
        pass

    #######################
    @abc.abstractmethod
    def build( self ):
        return

class ComputeTaskDef:
    #######################
    def __init__( self ):
        self.taskId             = ""
        self.subtaskId          = ""
        self.srcCode            = ""
        self.extraData          = {}
        self.shortDescription   = ""
        self.returnAddress      = ""
        self.returnPort         = 0
        self.workingDirectory   = ""
        self.performance        = 0.0
        self.environment        = ""

class Task:
    #######################
    def __init__( self, header, srcCode ):
        self.srcCode    = srcCode
        self.header     = header

    #######################
    @abc.abstractmethod
    def initialize( self ):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def queryExtraData( self, perfIndex, numCores = 1, clientId = None ):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def shortExtraDataRepr( self, perfIndex ):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def needsComputation( self ):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def computationStarted( self, extraData ):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def computationFinished( self, subtaskId, taskResult, dirManager = None ):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def verifySubtask( self, subtaskId ):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def verifyTask( self ):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def getTotalTasks( self ):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def getTotalChunks( self ):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def getActiveTasks( self ):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def getActiveChunks( self ):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def getChunksLeft( self ):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def getProgress( self ):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def acceptResultsDelay( self ):
        return 0.0

    #######################
    @abc.abstractmethod
    def prepareResourceDelta( self, taskId, resourceHeader ):
        return None

    #######################
    @abc.abstractmethod
    def testTask( self ):
        return False

    @abc.abstractmethod
    def updateTaskState( self, taskState ):
        return

    @abc.abstractmethod
    def getPriceMode( self, subtaskId ):
        return

    #######################
    @classmethod
    def buildTask( cls, taskBuilder ):
        assert isinstance( taskBuilder, TaskBuilder )
        return taskBuilder.build()

