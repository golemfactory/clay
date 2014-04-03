
import time
import abc

class TaskHeader:
    #######################
    def __init__( self, id, taskOwnerAddress, taskOwnerPort, ttl = 0.0 ):
        self.id = id
        self.taskOwnerAddress = taskOwnerAddress
        self.taskOwnerPort = taskOwnerPort
        self.lastChecking = time.time()
        self.ttl = ttl

class Task:
    #######################
    def __init__( self, header, srcCode ):
        self.srcCode = srcCode
        self.header = header

    #######################
    @abc.abstractmethod
    def initialize( self ):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def queryExtraData( self, perfIndex ):
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
    def computationFinished( self, extraData, taskResult ):
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
