import time
import logging

from golem.manager.NodeStateSnapshot import LocalTaskStateSnapshot
from golem.task.TaskState import TaskState, TaskStatus, SubtaskStatus, SubtaskState, ComputerState
from golem.resource.DirManager import DirManager
from golem.core.hostaddress import get_external_address

logger = logging.getLogger(__name__)

class TaskManagerEventListener:
    #######################
    def __init__(self):
        pass

    #######################
    def taskStatusUpdated(self, taskId):
        pass

    #######################
    def subtaskStatusUpdated(self, subtaskId):
        pass


class TaskManager:
    #######################
    def __init__(self, clientUid, node, listenAddress = "", listenPort = 0, keyId = "", rootPath = "res", useDistributedResources=True):
        self.clientUid      = clientUid
        self.node = node

        self.tasks          = {}
        self.tasksStates    = {}

        self.listenAddress  = listenAddress
        self.listenPort     = listenPort
        self.keyId          = keyId

        self.rootPath = rootPath
        self.dirManager     = DirManager(self.getTaskManagerRoot(), self.clientUid)

        self.subTask2TaskMapping = {}

        self.listeners      = []
        self.activeStatus = [TaskStatus.computing, TaskStatus.starting, TaskStatus.waiting]

        self.useDistributedResources = useDistributedResources

    #######################
    def getTaskManagerRoot(self):
        return self.rootPath

    #######################
    def registerListener(self, listener):
        assert isinstance(listener, TaskManagerEventListener)

        if listener in self.listeners:
            logger.error("listener {} already registered ".format(listener))
            return

        self.listeners.append(listener)

    #######################
    def unregisterListener(self, listener):
        for i in range(len(self.listeners)):
            if self.listeners[i] is listener:
                del self.listeners[i]
                return

    #######################
    def addNewTask(self, task):
        assert task.header.taskId not in self.tasks

        task.header.taskOwnerAddress = self.listenAddress
        task.header.taskOwnerPort = self.listenPort
        task.header.taskOwnerKeyId = self.keyId
        self.node.pubAddr, self.node.pubPort, self.node.natType = get_external_address(self.listenPort)
        task.header.taskOwner = self.node

        task.initialize()
        self.tasks[task.header.taskId] = task

        self.dirManager.clearTemporary(task.header.taskId)
        self.dirManager.getTaskTemporaryDir(task.header.taskId, create = True)

        ts              = TaskState()
        if self.useDistributedResources:
            task.taskStatus = TaskStatus.sending
            ts.status       = TaskStatus.sending
        else:
            task.taskStatus = TaskStatus.waiting
            ts.status       = TaskStatus.waiting
        ts.timeStarted  = time.time()

        self.tasksStates[task.header.taskId] = ts

        self.__noticeTaskUpdated(task.header.taskId)

    #######################
    def resourcesSend(self, taskId):
        self.tasksStates[taskId].status = TaskStatus.waiting
        self.tasks[taskId].taskStatus = TaskStatus.waiting
        self.__noticeTaskUpdated(taskId)
        logger.info("Resources for task {} send".format(taskId))

    #######################
    def getNextSubTask(self, clientId, taskId, estimatedPerformance, maxResourceSize, maxMemorySize, numCores = 0):
        if taskId in self.tasks:
            task = self.tasks[taskId]
            ts = self.tasksStates[taskId]
            th = task.header
            if self.__hasSubtasks(ts, task, maxResourceSize, maxMemorySize):
                ctd  = task.queryExtraData(estimatedPerformance, numCores, clientId)
                if ctd is None or ctd.subtaskId is None:
                    return None, False
                ctd.keyId = th.taskOwnerKeyId
                self.subTask2TaskMapping[ctd.subtaskId] = taskId
                self.__addSubtaskToTasksStates(clientId, ctd)
                self.__noticeTaskUpdated(taskId)
                return ctd, False
            logger.info("Cannot get next task for estimated performence {}".format(estimatedPerformance))
            return None, False
        else:
            logger.info("Cannot find task {} in my tasks".format(taskId))
            return None, True

    #######################
    def getTasksHeaders(self):
        ret = []
        for t in self.tasks.values():
            if t.needsComputation() and t.taskStatus in self.activeStatus:
                ret.append(t.header)

        return ret

    #######################
    def getPriceMod(self, subtaskId):
        if subtaskId in self.subTask2TaskMapping:
            taskId = self.subTask2TaskMapping[subtaskId]
            return self.tasks[taskId].getPriceMod(subtaskId)
        else:
            logger.error("This is not my subtask {}".format(subtaskId))
            return 0

    #######################
    def getTrustMod(self, subtaskId):
        if subtaskId in self.subTask2TaskMapping:
            taskId = self.subTask2TaskMapping[subtaskId]
            return self.tasks[taskId].getTrustMod(subtaskId)
        else:
            logger.error("This is not my subtask {}".format(subtaskId))
            return 0

    #######################
    def verifySubtask(self, subtaskId):
        if subtaskId in self.subTask2TaskMapping:
            taskId = self.subTask2TaskMapping[subtaskId]
            return self.tasks[taskId].verifySubtask(subtaskId)
        else:
            return False

    #######################
    def getNodeIdForSubtask(self, subtaskId):
        if subtaskId in self.subTask2TaskMapping:
            subtaskState = self.tasksStates[self.subTask2TaskMapping[subtaskId]].subtaskStates[subtaskId]
            return subtaskState.computer.nodeId
        else:
            return None

    #######################
    def computedTaskReceived(self, subtaskId, result, resultType):
        if subtaskId in self.subTask2TaskMapping:
            taskId = self.subTask2TaskMapping[subtaskId]

            subtaskStatus = self.tasksStates[taskId].subtaskStates[subtaskId].subtaskStatus
            if  subtaskStatus != SubtaskStatus.starting:
                logger.warning("Result for subtask {} when subtask state is {}".format(subtaskId, subtaskStatus))
                self.__noticeTaskUpdated(taskId)
                return False

            self.tasks[taskId].computationFinished(subtaskId, result, self.dirManager, resultType)
            ss = self.tasksStates[taskId].subtaskStates[subtaskId]
            ss.subtaskProgress  = 1.0
            ss.subtaskRemTime   = 0.0
            ss.subtaskStatus    = SubtaskStatus.finished

            if not self.tasks [taskId].verifySubtask(subtaskId):
                logger.debug("Subtask {} not accepted\n".format(subtaskId))
                ss.subtaskStatus = SubtaskStatus.failure
                self.__noticeTaskUpdated(taskId)
                return False

            if self.tasksStates[taskId].status in self.activeStatus:
                if not self.tasks[taskId].finishedComputation():
                    self.tasksStates[taskId].status = TaskStatus.computing
                else:
                    if self.tasks[taskId].verifyTask():
                        logger.debug("Task {} accepted".format(taskId))
                        self.tasksStates[taskId].status = TaskStatus.finished
                    else:
                        logger.debug("Task {} not accepted".format(taskId))
                    self.__noticeTaskFinished(taskId)
            self.__noticeTaskUpdated(taskId)

            return True
        else:
            logger.error("It is not my task id {}".format(subtaskId))
            return False

    #######################
    def taskComputationFailure(self, subtaskId, err):
        if subtaskId in self.subTask2TaskMapping:
            taskId = self.subTask2TaskMapping[subtaskId]
            subtaskStatus = self.tasksStates[taskId].subtaskStates[subtaskId].subtaskStatus
            if  subtaskStatus != SubtaskStatus.starting:
                logger.warning("Result for subtask {} when subtask state is {}".format(subtaskId, subtaskStatus))
                self.__noticeTaskUpdated(taskId)
                return False

            self.tasks[taskId].computationFailed(subtaskId)
            ss = self.tasksStates[taskId].subtaskStates[subtaskId]
            ss.subtaskProgress = 1.0
            ss.subtaskRemTime = 0.0
            ss.subtaskStatus = SubtaskStatus.failure

            self.__noticeTaskUpdated(taskId)
            return True
        else:
            logger.error("It is not my task id {}".format(subtaskId))
            return False

    #######################
    def removeOldTasks(self):
        nodesWithTimeouts = []
        for t in self.tasks.values():
            th = t.header
            if self.tasksStates[th.taskId].status not in self.activeStatus:
                continue
            currTime = time.time()
            th.ttl = th.ttl - (currTime - th.lastChecking)
            th.lastChecking = currTime
            if th.ttl <= 0:
                logger.info("Task {} dies".format(th.taskId))
                del self.tasks[th.taskId]
                continue
            ts = self.tasksStates[th.taskId]
            for s in ts.subtaskStates.values():
                if s.subtaskStatus == SubtaskStatus.starting:
                    s.ttl = s.ttl - (currTime - s.lastChecking)
                    s.lastChecking = currTime
                    if s.ttl <= 0:
                        logger.info("Subtask {} dies".format(s.subtaskId))
                        s.subtaskStatus        = SubtaskStatus.failure
                        nodesWithTimeouts.append(s.computer.nodeId)
                        t.computationFailed(s.subtaskId)
                        self.__noticeTaskUpdated(th.taskId)
        return nodesWithTimeouts



    #######################
    def getProgresses(self):
        tasksProgresses = {}

        for t in self.tasks.values():
            if t.getProgress() < 1.0:
                ltss = LocalTaskStateSnapshot(t.header.taskId, t.getTotalTasks(), t.getTotalChunks(), t.getActiveTasks(), t.getActiveChunks(), t.getChunksLeft(), t.getProgress(), t.shortExtraDataRepr(2200.0))
                tasksProgresses[t.header.taskId] = ltss

        return tasksProgresses

    #######################
    def prepareResource(self, taskId, resourceHeader):
        if taskId in self.tasks:
            task = self.tasks[taskId]
            return task.prepareResourceDelta(taskId, resourceHeader)

    #######################
    def getResourcePartsList(self, taskId, resourceHeader):
        if taskId in self.tasks:
            task = self.tasks[taskId]
            return task.getResourcePartsList(taskId, resourceHeader)

    #######################
    def acceptResultsDelay(self, taskId):
        if taskId in self.tasks:
            return self.tasks[taskId].acceptResultsDelay()
        else:
            return -1.0

    #######################
    def restartTask(self, taskId):
        if taskId in self.tasks:
            logger.info("restarting task")
            self.dirManager.clearTemporary(taskId)

            self.tasks[taskId].restart()
            self.tasks[taskId].taskStatus = TaskStatus.waiting
            self.tasksStates[taskId].status = TaskStatus.waiting
            self.tasksStates[taskId].timeStarted = time.time()

            for sub in self.tasksStates[taskId].subtaskStates.values():
                del self.subTask2TaskMapping[sub.subtaskId]
            self.tasksStates[taskId].subtaskStates.clear()

            self.__noticeTaskUpdated(taskId)
        else:
            logger.error("Task {} not in the active tasks queue ".format(taskId))

    #######################
    def restartSubtask(self, subtaskId):
        if not subtaskId in self.subTask2TaskMapping:
            logger.error("Subtask {} not in subtasks queue".format(subtaskId))
            return

        taskId = self.subTask2TaskMapping[subtaskId]
        self.tasks[taskId].restartSubtask(subtaskId)
        self.tasksStates[taskId].status = TaskStatus.computing
        self.tasksStates[taskId].subtaskStates[subtaskId].subtaskStatus = SubtaskStatus.failure

        self.__noticeTaskUpdated(taskId)

    #######################
    def abortTask(self, taskId):
        if taskId in self.tasks:
            self.tasks[taskId].abort()
            self.tasks[taskId].taskStatus = TaskStatus.aborted
            self.tasksStates[taskId].status = TaskStatus.aborted
            for sub in self.tasksStates[taskId].subtaskStates.values():
                del self.subTask2TaskMapping[sub.subtaskId]
            self.tasksStates[taskId].subtaskStates.clear()

            self.__noticeTaskUpdated(taskId)
        else:
            logger.error("Task {} not in the active tasks queue ".format(taskId))

    #######################
    def pauseTask(self, taskId):
        if taskId in self.tasks:
            self.tasks[taskId].taskStatus = TaskStatus.paused
            self.tasksStates[taskId].status = TaskStatus.paused

            self.__noticeTaskUpdated(taskId)
        else:
            logger.error("Task {} not in the active tasks queue ".format(taskId))


    #######################
    def resumeTask(self, taskId):
        if taskId in self.tasks:
            self.tasks[taskId].taskStatus = TaskStatus.starting
            self.tasksStates[taskId].status = TaskStatus.starting

            self.__noticeTaskUpdated(taskId)
        else:
            logger.error("Task {} not in the active tasks queue ".format(taskId))

    #######################
    def deleteTask(self, taskId):
        if taskId in self.tasks:

            for sub in self.tasksStates[taskId].subtaskStates.values():
                del self.subTask2TaskMapping[sub.subtaskId]
            self.tasksStates[taskId].subtaskStates.clear()

            del self.tasks[taskId]
            del self.tasksStates[taskId]

            self.dirManager.clearTemporary(taskId)
        else:
            logger.error("Task {} not in the active tasks queue ".format(taskId))

    #######################
    def querryTaskState(self, taskId):
        if taskId in self.tasksStates and taskId in self.tasks:
            ts  = self.tasksStates[taskId]
            t   = self.tasks[taskId]

            ts.progress = t.getProgress()
            ts.elapsedTime = time.time() - ts.timeStarted

            if ts.progress > 0.0:
                ts.remainingTime =  (ts.elapsedTime / ts.progress) - ts.elapsedTime
            else:
                ts.remainingTime = -0.0

            t.updateTaskState(ts)

            return ts
        else:
            assert False, "Should never be here!"
            return None

    #######################
    def change_config(self, rootPath, useDistributedResourceManagement):
        self.dirManager = DirManager(rootPath, self.clientUid)
        self.useDistributedResources = useDistributedResourceManagement

    #######################
    def changeTimeouts(self, taskId, fullTaskTimeout, subtaskTimeout, minSubtaskTime):
        if taskId in self.tasks:
            task = self.tasks[taskId]
            task.header.ttl = fullTaskTimeout
            task.header.subtaskTimeout = subtaskTimeout
            task.subtaskTimeout = subtaskTimeout
            task.minSubtaskTime = minSubtaskTime
            task.fullTaskTimeout = fullTaskTimeout
            task.header.lastChecking = time.time()
            ts = self.tasksStates[taskId]
            for s in ts.subtaskStates.values():
                s.ttl = subtaskTimeout
                s.lastChecking = time.time()
            return True
        else:
            logger.info("Cannot find task {} in my tasks".format(taskId))
            return False

    #######################
    def getTaskId(self, subtaskId):
        return self.subTask2TaskMapping[subtaskId]


    #######################
    def __addSubtaskToTasksStates(self, clientId, ctd):

        if ctd.taskId not in self.tasksStates:
            assert False, "Should never be here!"
        else:
            ts = self.tasksStates[ctd.taskId]

            ss                      = SubtaskState()
            ss.computer.nodeId      = clientId
            ss.computer.performance = ctd.performance
            ss.timeStarted      = time.time()
            ss.ttl              = self.tasks[ctd.taskId].header.subtaskTimeout
            # TODO: read node ip address
            ss.subtaskDefinition    = ctd.shortDescription
            ss.subtaskId            = ctd.subtaskId
            ss.extraData            = ctd.extraData
            ss.subtaskStatus        = TaskStatus.starting
            ss.value                = 0

            ts.subtaskStates[ctd.subtaskId] = ss

    #######################
    def __noticeTaskUpdated(self, taskId):
        for l in self.listeners:
            l.taskStatusUpdated(taskId)

    #######################
    def __noticeTaskFinished(self, taskId):
        for l in self.listeners:
            l.taskFinished(taskId)

    #######################
    def __hasSubtasks(self, taskState, task, maxResourceSize, maxMemorySize):
        if taskState.status not in self.activeStatus:
            return False
        if not task.needsComputation():
            return False
        if task.header.resourceSize > (long(maxResourceSize) * 1024):
            return False
        if task.header.estimatedMemory > (long(maxMemorySize) * 1024):
            return False
        return True
