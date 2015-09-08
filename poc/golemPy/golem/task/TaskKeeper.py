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
        self.supported_tasks = []
        self.removedTasks   = {}
        self.activeTasks    = {}
        self.activeRequests = {}
        self.waitingForVerification = {}

        self.verificationTimeout = verificationTimeout
        self.removedTaskTimeout = removeTaskTimeout

    #############################
    def get_task(self):
        if  len(self.supported_tasks) > 0:
            tn = random.randrange(0, len(self.supported_tasks))
            task_id = self.supported_tasks[tn]
            theader = self.taskHeaders[task_id]
            if task_id in self.activeRequests:
                self.activeRequests[task_id] += 1
            else:
                self.activeTasks[task_id] = theader
                self.activeRequests[task_id] = 1
            return theader
        else:
            return None

    #############################
    def getAllTasks(self):
        return self.taskHeaders.values()

    #############################
    def add_task_header(self, th_dict_repr, is_supported):
        try:
            id = th_dict_repr["id"]
            if id not in self.taskHeaders.keys(): # dont have it
                if id not in self.removedTasks.keys(): # not removed recently
                    logger.info("Adding task {}".format(id))
                    self.taskHeaders[id] = TaskHeader(th_dict_repr["client_id"], id, th_dict_repr["address"],
                                                      th_dict_repr["port"], th_dict_repr["key_id"],
                                                      th_dict_repr["environment"], th_dict_repr["taskOwner"],
                                                      th_dict_repr[ "ttl" ], th_dict_repr["subtask_timeout"])
                    if is_supported:
                        self.supported_tasks.append(id)
            return True
        except Exception, err:
            logger.error("Wrong task header received {}".format(str(err)))
            return False

    ###########################
    def remove_task_header(self, task_id):
        if task_id in self.taskHeaders:
            del self.taskHeaders[task_id]
        if task_id in self.supported_tasks:
           self.supported_tasks.remove(task_id)
        self.removedTasks[task_id] = time.time()
        if task_id in self.activeRequests and self.activeRequests[task_id] <= 0:
            self.__delActiveTask(task_id)

    #############################
    def get_subtask_ttl(self, task_id):
        if task_id in self.taskHeaders:
            return self.taskHeaders[task_id].subtask_timeout

    ###########################
    def receive_task_verification(self, task_id):
        if task_id not in self.activeTasks:
            logger.warning("Wasn't waiting for verification result for {}").format(task_id)
            return
        self.activeRequests[task_id] -= 1
        if self.activeRequests[task_id] <= 0 and task_id not in self.taskHeaders:
            self.__delActiveTask(task_id)

    ############################
    def getWaitingForVerificationTaskId(self, subtask_id):
        if subtask_id not in self.waitingForVerification:
            return None
        return self.waitingForVerification[subtask_id][0]

    ############################
    def isWaitingForTask(self, task_id):
        for v in self.waitingForVerification.itervalues():
            if v[0] == task_id:
                return True
        return False

    ############################
    def removeWaitingForVerification(self, task_id):
        subtasks = [subId for subId, val in self.waitingForVerification.iteritems() if val[0] == task_id ]
        for subtask_id in subtasks:
            del self.waitingForVerification[ subtask_id ]

    ############################
    def removeWaitingForVerificationTaskId(self, subtask_id):
        if subtask_id in self.waitingForVerification:
            del self.waitingForVerification[subtask_id]

    ############################
    def removeOldTasks(self):
        for t in self.taskHeaders.values():
            currTime = time.time()
            t.ttl = t.ttl - (currTime - t.last_checking)
            t.last_checking = currTime
            if t.ttl <= 0:
                logger.warning("Task {} dies".format(t.task_id))
                self.remove_task_header(t.task_id)

        for task_id, removeTime in self.removedTasks.items():
            currTime = time.time()
            if currTime - removeTime > self.removedTaskTimeout:
                del self.removedTasks[task_id]

    ############################
    def request_failure(self, task_id):
        if task_id in self.activeRequests:
            self.activeRequests[task_id] -= 1
        self.remove_task_header(task_id)

    ###########################
    def getReceiverForTaskVerificationResult(self, task_id):
        if task_id not in self.activeTasks:
            return None
        return self.activeTasks[task_id].client_id

    ###########################
    def addToVerification(self, subtask_id, task_id):
        now = datetime.datetime.now()
        self.waitingForVerification[ subtask_id ] = [task_id, now, self.__countDeadline(now)]

    #############################
    def checkPayments(self):
        now = datetime.datetime.now()
        afterDeadline = []
        for subtask_id, [task_id, taskDate, deadline] in self.waitingForVerification.items():
            if deadline < now:
                afterDeadline.append(task_id)
                del self.waitingForVerification[subtask_id]
        return afterDeadline

    ###########################
    def __countDeadline(self, date): #FIXME Cos zdecydowanie bardziej zaawansowanego i moze dopasowanego do kwoty
        return datetime.datetime.fromtimestamp(time.time() + self.verificationTimeout)

    ###########################
    def __delActiveTask(self, task_id):
        del self.activeTasks[task_id]
        del self.activeRequests[task_id]
