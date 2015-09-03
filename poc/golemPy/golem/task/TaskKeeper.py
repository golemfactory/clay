import logging
import random
import time
import datetime

from TaskBase import TaskHeader

logger = logging.getLogger(__name__)

class TaskKeeper:
    #############################
    def __init__(self, removeTaskTimeout = 240.0, verificationTimeout = 3600):
        self.taskHeaders    = {}
        self.supportedTasks = []
        self.removedTasks   = {}
        self.activeTasks    = {}
        self.activeRequests = {}
        self.waitingForVerification = {}

        self.verificationTimeout = verificationTimeout
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
    def getAllTasks(self):
        return self.taskHeaders.values()

    #############################
    def add_task_header(self, th_dict_repr, isSupported):
        try:
            id = th_dict_repr["id"]
            if id not in self.taskHeaders.keys(): # dont have it
                if id not in self.removedTasks.keys(): # not removed recently
                    logger.info("Adding task {}".format(id))
                    self.taskHeaders[id] = TaskHeader(th_dict_repr["client_id"], id, th_dict_repr["address"],
                                                      th_dict_repr["port"], th_dict_repr["keyId"],
                                                      th_dict_repr["environment"], th_dict_repr["taskOwner"],
                                                      th_dict_repr[ "ttl" ], th_dict_repr["subtaskTimeout"])
                    if isSupported:
                        self.supportedTasks.append(id)
            return True
        except Exception, err:
            logger.error("Wrong task header received {}".format(str(err)))
            return False

    ###########################
    def remove_task_header(self, taskId):
        if taskId in self.taskHeaders:
            del self.taskHeaders[taskId]
        if taskId in self.supportedTasks:
           self.supportedTasks.remove(taskId)
        self.removedTasks[taskId] = time.time()
        if taskId in self.activeRequests and self.activeRequests[taskId] <= 0:
            self.__delActiveTask(taskId)

    #############################
    def getSubtaskTtl(self, taskId):
        if taskId in self.taskHeaders:
            return self.taskHeaders[taskId].subtaskTimeout

    ###########################
    def receiveTaskVerification(self, taskId):
        if taskId not in self.activeTasks:
            logger.warning("Wasn't waiting for verification result for {}").format(taskId)
            return
        self.activeRequests[taskId] -= 1
        if self.activeRequests[taskId] <= 0 and taskId not in self.taskHeaders:
            self.__delActiveTask(taskId)

    ############################
    def getWaitingForVerificationTaskId(self, subtaskId):
        if subtaskId not in self.waitingForVerification:
            return None
        return self.waitingForVerification[subtaskId][0]

    ############################
    def isWaitingForTask(self, taskId):
        for v in self.waitingForVerification.itervalues():
            if v[0] == taskId:
                return True
        return False

    ############################
    def removeWaitingForVerification(self, taskId):
        subtasks = [subId for subId, val in self.waitingForVerification.iteritems() if val[0] == taskId ]
        for subtaskId in subtasks:
            del self.waitingForVerification[ subtaskId ]

    ############################
    def removeWaitingForVerificationTaskId(self, subtaskId):
        if subtaskId in self.waitingForVerification:
            del self.waitingForVerification[subtaskId]

    ############################
    def removeOldTasks(self):
        for t in self.taskHeaders.values():
            currTime = time.time()
            t.ttl = t.ttl - (currTime - t.lastChecking)
            t.lastChecking = currTime
            if t.ttl <= 0:
                logger.warning("Task {} dies".format(t.taskId))
                self.remove_task_header(t.taskId)

        for taskId, removeTime in self.removedTasks.items():
            currTime = time.time()
            if currTime - removeTime > self.removedTaskTimeout:
                del self.removedTasks[taskId]

    ############################
    def requestFailure(self, taskId):
        if taskId in self.activeRequests:
            self.activeRequests[taskId] -= 1
        self.remove_task_header(taskId)

    ###########################
    def getReceiverForTaskVerificationResult(self, taskId):
        if taskId not in self.activeTasks:
            return None
        return self.activeTasks[taskId].client_id

    ###########################
    def addToVerification(self, subtaskId, taskId):
        now = datetime.datetime.now()
        self.waitingForVerification[ subtaskId ] = [taskId, now, self.__countDeadline(now)]

    #############################
    def checkPayments(self):
        now = datetime.datetime.now()
        afterDeadline = []
        for subtaskId, [taskId, taskDate, deadline] in self.waitingForVerification.items():
            if deadline < now:
                afterDeadline.append(taskId)
                del self.waitingForVerification[subtaskId]
        return afterDeadline

    ###########################
    def __countDeadline(self, date): #FIXME Cos zdecydowanie bardziej zaawansowanego i moze dopasowanego do kwoty
        return datetime.datetime.fromtimestamp(time.time() + self.verificationTimeout)

    ###########################
    def __delActiveTask(self, taskId):
        del self.activeTasks[taskId]
        del self.activeRequests[taskId]
