import logging
import random
import time

from TaskBase import TaskHeader

logger = logging.getLogger( __name__ )

class TaskKeeper:
    #############################
    def __init__( self, removeTaskTimeout = 240.0 ):
        self.taskHeaders    = {}
        self.supportedTasks = []
        self.removedTasks   = {}
        self.activeTasks    = {}
        self.activeRequests = {}
        self.waitingForVerification = {}

        self.removedTaskTimeout = removeTaskTimeout

    #############################
    def getTask(self):
        if  len(self.supportedTasks) > 0:
            tn = random.randrange(0, len(self.supportedTasks))
            taskId = self.supportedTasks[tn]
            theader = self.taskHeaders[taskId]
            if taskId in self.activeRequests:
                self.activeRequests[taskId] += 1
            else:
                self.activeTasks[taskId] = theader
                self.activeRequests[taskId] = 1
            return theader
        else:
            return None

    #############################
    def getAllTasks( self ):
        return self.taskHeaders.values()

    #############################
    def addTaskHeader( self, thDictRepr, isSupported ):
        try:
            id = thDictRepr["id"]
            if id not in self.taskHeaders.keys(): # dont have it
                if id not in self.removedTasks.keys(): # not removed recently
                    logger.info( "Adding task {}".format( id ) )
                    self.taskHeaders[ id ] = TaskHeader( thDictRepr[ "clientId" ], id, thDictRepr[ "address" ], thDictRepr[ "port" ], thDictRepr["environment"], thDictRepr[ "ttl" ], thDictRepr["subtaskTimeout"] )
                    if isSupported:
                        self.supportedTasks.append( id )
            return True
        except Exception, err:
            logger.error( "Wrong task header received {}".format( str( err ) ) )
            return False

    ###########################
    def removeTaskHeader(self, taskId):
        if taskId in self.taskHeaders:
            del self.taskHeaders[taskId]
        if taskId in self.supportedTasks:
           self.supportedTasks.remove(taskId)
        self.removedTasks[taskId] = time.time()
        if taskId in self.activeRequests and self.activeRequests[taskId] <= 0:
            self.__delActiveTask(taskId)

    ###########################
    def receiveTaskVerification( self, taskId ):
        if taskId not in self.activeTasks:
            logger.warning("Wasn't waiting for verification result for {}").format( taskId )
            return
        self.activeRequests[taskId] -= 1
        if self.activeRequests[taskId] <= 0 and taskId not in self.taskHeaders:
            self.__delActiveTask(taskId)

    ############################
    def getWaitingForVerificationTaskId(self, subtaskId):
        if subtaskId not in self.waitingForVerification:
            return None
        return self.waitingForVerification[subtaskId]

    ############################
    def removeWaitingForVerificationTaskId(self, subtaskId):
        if subtaskId in self.waitingForVerification:
            del self.waitingForVerification[subtaskId]

    ############################
    def removeOldTasks( self ):
        for t in self.taskHeaders.values():
            currTime = time.time()
            t.ttl = t.ttl - ( currTime - t.lastChecking )
            t.lastChecking = currTime
            if t.ttl <= 0:
                logger.warning( "Task {} dies".format( t.taskId ) )
                self.removeTaskHeader( t.taskId )

        for taskId, removeTime in self.removedTasks.items():
            currTime = time.time()
            if currTime - removeTime > self.removedTaskTimeout:
                del self.removedTasks[taskId]

    ############################
    def requestFailure(self, taskId ):
        if taskId in self.activeRequests:
            self.activeRequests[taskId] -= 1
        self.removeTaskHeader(taskId)

    ###########################
    def getReceiverForTaskVerificationResult( self, taskId ):
        if taskId not in self.activeTasks:
            return None
        return self.activeTasks[taskId].clientId

    def addToVerification( self, subtaskId, taskId ):
        self.waitingForVerification[ subtaskId ] = taskId

    ###########################
    def __delActiveTask(self, taskId):
        del self.activeTasks[taskId]
        del self.activeRequests[taskId]
