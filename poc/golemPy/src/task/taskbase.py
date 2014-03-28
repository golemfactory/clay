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
    def __init__( self, header, resources, codeRes, outputSize ):
        self.resources = resources
        self.codeRes = codeRes
        self.header = header
        self.taskResult = None
        self.outputSize = outputSize

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
