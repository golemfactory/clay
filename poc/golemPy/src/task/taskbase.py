import time

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
    def queryExtraData( self, perfIndex ):
        assert False # Implement in derived class

    #######################
    def needsComputation( self ):
        assert False # Implement in derived class

    #######################
    def computationStarted( self, extraData ):
        assert False # Implement in derived class

    #######################
    def computationFinished( self, extraData, taskResult ):
        assert False # Implement in derived class

    #######################
    def getTotalTasks( self ):
        assert False # Implement in derived class

    #######################
    def getTotalChunks( self ):
        assert False # Implement in derived class

    #######################
    def getActiveTasks( self ):
        assert False # Implement in derived class

    #######################
    def getActiveChunks( self ):
        assert False # Implement in derived class

    #######################
    def getChunksLeft( self ):
        assert False # Implement in derived class

    #######################
    def getProgress( self ):
        assert False # Implement in derived class


