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
    def taskStatusUpdated(self, task_id):
        pass

    #######################
    def subtaskStatusUpdated(self, subtask_id):
        pass


class TaskManager:
    #######################
    def __init__(self, client_uid, node, listenAddress = "", listenPort = 0, key_id = "", root_path = "res", useDistributedResources=True):
        self.client_uid      = client_uid
        self.node = node

        self.tasks          = {}
        self.tasksStates    = {}

        self.listenAddress  = listenAddress
        self.listenPort     = listenPort
        self.keyId          = key_id

        self.root_path = root_path
        self.dir_manager     = DirManager(self.getTaskManagerRoot(), self.client_uid)

        self.subTask2TaskMapping = {}

        self.listeners      = []
        self.activeStatus = [TaskStatus.computing, TaskStatus.starting, TaskStatus.waiting]

        self.useDistributedResources = useDistributedResources

    #######################
    def getTaskManagerRoot(self):
        return self.root_path

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
        assert task.header.task_id not in self.tasks

        task.header.taskOwnerAddress = self.listenAddress
        task.header.taskOwnerPort = self.listenPort
        task.header.taskOwnerKeyId = self.keyId
        self.node.pubAddr, self.node.pubPort, self.node.natType = get_external_address(self.listenPort)
        task.header.taskOwner = self.node

        task.initialize()
        self.tasks[task.header.task_id] = task

        self.dir_manager.clearTemporary(task.header.task_id)
        self.dir_manager.getTaskTemporaryDir(task.header.task_id, create = True)

        ts              = TaskState()
        if self.useDistributedResources:
            task.taskStatus = TaskStatus.sending
            ts.status       = TaskStatus.sending
        else:
            task.taskStatus = TaskStatus.waiting
            ts.status       = TaskStatus.waiting
        ts.timeStarted  = time.time()

        self.tasksStates[task.header.task_id] = ts

        self.__noticeTaskUpdated(task.header.task_id)

    #######################
    def resourcesSend(self, task_id):
        self.tasksStates[task_id].status = TaskStatus.waiting
        self.tasks[task_id].taskStatus = TaskStatus.waiting
        self.__noticeTaskUpdated(task_id)
        logger.info("Resources for task {} send".format(task_id))

    #######################
    def getNextSubTask(self, client_id, task_id, estimated_performance, max_resource_size, max_memory_size, num_cores = 0):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            ts = self.tasksStates[task_id]
            th = task.header
            if self.__hasSubtasks(ts, task, max_resource_size, max_memory_size):
                ctd  = task.queryExtraData(estimated_performance, num_cores, client_id)
                if ctd is None or ctd.subtask_id is None:
                    return None, False
                ctd.keyId = th.taskOwnerKeyId
                self.subTask2TaskMapping[ctd.subtask_id] = task_id
                self.__addSubtaskToTasksStates(client_id, ctd)
                self.__noticeTaskUpdated(task_id)
                return ctd, False
            logger.info("Cannot get next task for estimated performence {}".format(estimated_performance))
            return None, False
        else:
            logger.info("Cannot find task {} in my tasks".format(task_id))
            return None, True

    #######################
    def get_tasks_headers(self):
        ret = []
        for t in self.tasks.values():
            if t.needsComputation() and t.taskStatus in self.activeStatus:
                ret.append(t.header)

        return ret

    #######################
    def getPriceMod(self, subtask_id):
        if subtask_id in self.subTask2TaskMapping:
            task_id = self.subTask2TaskMapping[subtask_id]
            return self.tasks[task_id].getPriceMod(subtask_id)
        else:
            logger.error("This is not my subtask {}".format(subtask_id))
            return 0

    #######################
    def getTrustMod(self, subtask_id):
        if subtask_id in self.subTask2TaskMapping:
            task_id = self.subTask2TaskMapping[subtask_id]
            return self.tasks[task_id].getTrustMod(subtask_id)
        else:
            logger.error("This is not my subtask {}".format(subtask_id))
            return 0

    #######################
    def verifySubtask(self, subtask_id):
        if subtask_id in self.subTask2TaskMapping:
            task_id = self.subTask2TaskMapping[subtask_id]
            return self.tasks[task_id].verifySubtask(subtask_id)
        else:
            return False

    #######################
    def getNodeIdForSubtask(self, subtask_id):
        if subtask_id in self.subTask2TaskMapping:
            subtaskState = self.tasksStates[self.subTask2TaskMapping[subtask_id]].subtaskStates[subtask_id]
            return subtaskState.computer.node_id
        else:
            return None

    #######################
    def computedTaskReceived(self, subtask_id, result, resultType):
        if subtask_id in self.subTask2TaskMapping:
            task_id = self.subTask2TaskMapping[subtask_id]

            subtaskStatus = self.tasksStates[task_id].subtaskStates[subtask_id].subtaskStatus
            if  subtaskStatus != SubtaskStatus.starting:
                logger.warning("Result for subtask {} when subtask state is {}".format(subtask_id, subtaskStatus))
                self.__noticeTaskUpdated(task_id)
                return False

            self.tasks[task_id].computationFinished(subtask_id, result, self.dir_manager, resultType)
            ss = self.tasksStates[task_id].subtaskStates[subtask_id]
            ss.subtaskProgress  = 1.0
            ss.subtaskRemTime   = 0.0
            ss.subtaskStatus    = SubtaskStatus.finished

            if not self.tasks [task_id].verifySubtask(subtask_id):
                logger.debug("Subtask {} not accepted\n".format(subtask_id))
                ss.subtaskStatus = SubtaskStatus.failure
                self.__noticeTaskUpdated(task_id)
                return False

            if self.tasksStates[task_id].status in self.activeStatus:
                if not self.tasks[task_id].finishedComputation():
                    self.tasksStates[task_id].status = TaskStatus.computing
                else:
                    if self.tasks[task_id].verifyTask():
                        logger.debug("Task {} accepted".format(task_id))
                        self.tasksStates[task_id].status = TaskStatus.finished
                    else:
                        logger.debug("Task {} not accepted".format(task_id))
                    self.__noticeTaskFinished(task_id)
            self.__noticeTaskUpdated(task_id)

            return True
        else:
            logger.error("It is not my task id {}".format(subtask_id))
            return False

    #######################
    def taskComputation_failure(self, subtask_id, err):
        if subtask_id in self.subTask2TaskMapping:
            task_id = self.subTask2TaskMapping[subtask_id]
            subtaskStatus = self.tasksStates[task_id].subtaskStates[subtask_id].subtaskStatus
            if  subtaskStatus != SubtaskStatus.starting:
                logger.warning("Result for subtask {} when subtask state is {}".format(subtask_id, subtaskStatus))
                self.__noticeTaskUpdated(task_id)
                return False

            self.tasks[task_id].computationFailed(subtask_id)
            ss = self.tasksStates[task_id].subtaskStates[subtask_id]
            ss.subtaskProgress = 1.0
            ss.subtaskRemTime = 0.0
            ss.subtaskStatus = SubtaskStatus.failure

            self.__noticeTaskUpdated(task_id)
            return True
        else:
            logger.error("It is not my task id {}".format(subtask_id))
            return False

    #######################
    def removeOldTasks(self):
        nodes_with_timeouts = []
        for t in self.tasks.values():
            th = t.header
            if self.tasksStates[th.task_id].status not in self.activeStatus:
                continue
            currTime = time.time()
            th.ttl = th.ttl - (currTime - th.last_checking)
            th.last_checking = currTime
            if th.ttl <= 0:
                logger.info("Task {} dies".format(th.task_id))
                del self.tasks[th.task_id]
                continue
            ts = self.tasksStates[th.task_id]
            for s in ts.subtaskStates.values():
                if s.subtaskStatus == SubtaskStatus.starting:
                    s.ttl = s.ttl - (currTime - s.last_checking)
                    s.last_checking = currTime
                    if s.ttl <= 0:
                        logger.info("Subtask {} dies".format(s.subtask_id))
                        s.subtaskStatus        = SubtaskStatus.failure
                        nodes_with_timeouts.append(s.computer.node_id)
                        t.computationFailed(s.subtask_id)
                        self.__noticeTaskUpdated(th.task_id)
        return nodes_with_timeouts



    #######################
    def getProgresses(self):
        tasksProgresses = {}

        for t in self.tasks.values():
            if t.getProgress() < 1.0:
                ltss = LocalTaskStateSnapshot(t.header.task_id, t.getTotalTasks(), t.getTotalChunks(), t.getActiveTasks(), t.getActiveChunks(), t.getChunksLeft(), t.getProgress(), t.shortExtraDataRepr(2200.0))
                tasksProgresses[t.header.task_id] = ltss

        return tasksProgresses

    #######################
    def prepare_resource(self, task_id, resourceHeader):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            return task.prepare_resourceDelta(task_id, resourceHeader)

    #######################
    def getResourcePartsList(self, task_id, resourceHeader):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            return task.getResourcePartsList(task_id, resourceHeader)

    #######################
    def accept_results_delay(self, task_id):
        if task_id in self.tasks:
            return self.tasks[task_id].accept_results_delay()
        else:
            return -1.0

    #######################
    def restartTask(self, task_id):
        if task_id in self.tasks:
            logger.info("restarting task")
            self.dir_manager.clearTemporary(task_id)

            self.tasks[task_id].restart()
            self.tasks[task_id].taskStatus = TaskStatus.waiting
            self.tasksStates[task_id].status = TaskStatus.waiting
            self.tasksStates[task_id].timeStarted = time.time()

            for sub in self.tasksStates[task_id].subtaskStates.values():
                del self.subTask2TaskMapping[sub.subtask_id]
            self.tasksStates[task_id].subtaskStates.clear()

            self.__noticeTaskUpdated(task_id)
        else:
            logger.error("Task {} not in the active tasks queue ".format(task_id))

    #######################
    def restartSubtask(self, subtask_id):
        if not subtask_id in self.subTask2TaskMapping:
            logger.error("Subtask {} not in subtasks queue".format(subtask_id))
            return

        task_id = self.subTask2TaskMapping[subtask_id]
        self.tasks[task_id].restartSubtask(subtask_id)
        self.tasksStates[task_id].status = TaskStatus.computing
        self.tasksStates[task_id].subtaskStates[subtask_id].subtaskStatus = SubtaskStatus.failure

        self.__noticeTaskUpdated(task_id)

    #######################
    def abortTask(self, task_id):
        if task_id in self.tasks:
            self.tasks[task_id].abort()
            self.tasks[task_id].taskStatus = TaskStatus.aborted
            self.tasksStates[task_id].status = TaskStatus.aborted
            for sub in self.tasksStates[task_id].subtaskStates.values():
                del self.subTask2TaskMapping[sub.subtask_id]
            self.tasksStates[task_id].subtaskStates.clear()

            self.__noticeTaskUpdated(task_id)
        else:
            logger.error("Task {} not in the active tasks queue ".format(task_id))

    #######################
    def pauseTask(self, task_id):
        if task_id in self.tasks:
            self.tasks[task_id].taskStatus = TaskStatus.paused
            self.tasksStates[task_id].status = TaskStatus.paused

            self.__noticeTaskUpdated(task_id)
        else:
            logger.error("Task {} not in the active tasks queue ".format(task_id))


    #######################
    def resumeTask(self, task_id):
        if task_id in self.tasks:
            self.tasks[task_id].taskStatus = TaskStatus.starting
            self.tasksStates[task_id].status = TaskStatus.starting

            self.__noticeTaskUpdated(task_id)
        else:
            logger.error("Task {} not in the active tasks queue ".format(task_id))

    #######################
    def deleteTask(self, task_id):
        if task_id in self.tasks:

            for sub in self.tasksStates[task_id].subtaskStates.values():
                del self.subTask2TaskMapping[sub.subtask_id]
            self.tasksStates[task_id].subtaskStates.clear()

            del self.tasks[task_id]
            del self.tasksStates[task_id]

            self.dir_manager.clearTemporary(task_id)
        else:
            logger.error("Task {} not in the active tasks queue ".format(task_id))

    #######################
    def querryTaskState(self, task_id):
        if task_id in self.tasksStates and task_id in self.tasks:
            ts  = self.tasksStates[task_id]
            t   = self.tasks[task_id]

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
    def change_config(self, root_path, use_distributed_resource_management):
        self.dir_manager = DirManager(root_path, self.client_uid)
        self.useDistributedResources = use_distributed_resource_management

    #######################
    def change_timeouts(self, task_id, fullTaskTimeout, subtask_timeout, minSubtaskTime):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.header.ttl = fullTaskTimeout
            task.header.subtask_timeout = subtask_timeout
            task.subtask_timeout = subtask_timeout
            task.minSubtaskTime = minSubtaskTime
            task.fullTaskTimeout = fullTaskTimeout
            task.header.last_checking = time.time()
            ts = self.tasksStates[task_id]
            for s in ts.subtaskStates.values():
                s.ttl = subtask_timeout
                s.last_checking = time.time()
            return True
        else:
            logger.info("Cannot find task {} in my tasks".format(task_id))
            return False

    #######################
    def getTaskId(self, subtask_id):
        return self.subTask2TaskMapping[subtask_id]


    #######################
    def __addSubtaskToTasksStates(self, client_id, ctd):

        if ctd.task_id not in self.tasksStates:
            assert False, "Should never be here!"
        else:
            ts = self.tasksStates[ctd.task_id]

            ss                      = SubtaskState()
            ss.computer.node_id      = client_id
            ss.computer.performance = ctd.performance
            ss.timeStarted      = time.time()
            ss.ttl              = self.tasks[ctd.task_id].header.subtask_timeout
            # TODO: read node ip address
            ss.subtaskDefinition    = ctd.shortDescription
            ss.subtask_id            = ctd.subtask_id
            ss.extraData            = ctd.extraData
            ss.subtaskStatus        = TaskStatus.starting
            ss.value                = 0

            ts.subtaskStates[ctd.subtask_id] = ss

    #######################
    def __noticeTaskUpdated(self, task_id):
        for l in self.listeners:
            l.taskStatusUpdated(task_id)

    #######################
    def __noticeTaskFinished(self, task_id):
        for l in self.listeners:
            l.task_finished(task_id)

    #######################
    def __hasSubtasks(self, taskState, task, max_resource_size, max_memory_size):
        if taskState.status not in self.activeStatus:
            return False
        if not task.needsComputation():
            return False
        if task.header.resourceSize > (long(max_resource_size) * 1024):
            return False
        if task.header.estimatedMemory > (long(max_memory_size) * 1024):
            return False
        return True
