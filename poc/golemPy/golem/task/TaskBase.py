import time
import abc

class TaskHeader:
    #######################
    def __init__(self, client_id, taskId, taskOwnerAddress, taskOwnerPort, taskOwnerKeyId, environment, taskOwner = None, ttl = 0.0, subtask_timeout = 0.0, resourceSize = 0, estimatedMemory = 0, min_version = 1.0):
        self.taskId = taskId
        self.taskOwnerKeyId = taskOwnerKeyId
        self.taskOwnerAddress = taskOwnerAddress
        self.taskOwnerPort = taskOwnerPort
        self.taskOwner = taskOwner
        self.last_checking = time.time()
        self.ttl = ttl
        self.subtask_timeout = subtask_timeout
        self.client_id = client_id
        self.resourceSize = resourceSize
        self.environment = environment
        self.estimatedMemory = estimatedMemory
        self.min_version = min_version

class TaskBuilder:
    #######################
    def __init__(self):
        pass

    #######################
    @abc.abstractmethod
    def build(self):
        return

class ComputeTaskDef(object):
    #######################
    def __init__(self):
        self.taskId             = ""
        self.subtaskId          = ""
        self.srcCode            = ""
        self.extraData          = {}
        self.shortDescription   = ""
        self.returnAddress      = ""
        self.returnPort         = 0
        self.taskOwner          = None
        self.keyId              = 0
        self.workingDirectory   = ""
        self.performance        = 0.0
        self.environment        = ""

class Task:
    #######################
    def __init__(self, header, srcCode):
        self.srcCode    = srcCode
        self.header     = header

    #######################
    @abc.abstractmethod
    def initialize(self):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def queryExtraData(self, perfIndex, num_cores = 1, client_id = None):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def shortExtraDataRepr(self, perfIndex):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def needsComputation(self):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def computationStarted(self, extraData):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def computationFinished(self, subtaskId, taskResult, dir_manager = None, resultType = 0):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def computationFailed(self, subtaskId):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def verifySubtask(self, subtaskId):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def verifyTask(self):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def getTotalTasks(self):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def getTotalChunks(self):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def getActiveTasks(self):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def getActiveChunks(self):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def getChunksLeft(self):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def getProgress(self):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def accept_results_delay(self):
        return 0.0

    #######################
    @abc.abstractmethod
    def prepare_resourceDelta(self, taskId, resourceHeader):
        return None

    #######################
    @abc.abstractmethod
    def testTask(self):
        return False

    #######################
    @abc.abstractmethod
    def updateTaskState(self, taskState):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def getPriceMod(self, subtaskId):
        return # Implement in derived class

    #######################
    @abc.abstractmethod
    def getTrustMod(self, subtaskId):
        return # Implement in derived class

    #######################
    @classmethod
    def buildTask(cls, taskBuilder):
        assert isinstance(taskBuilder, TaskBuilder)
        return taskBuilder.build()

result_types = { 'data': 0, 'files': 1 }
