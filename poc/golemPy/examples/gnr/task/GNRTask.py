from golem.task.TaskBase import Task, TaskHeader, TaskBuilder, result_types
from golem.task.TaskState import SubtaskStatus
from golem.resource.Resource import prepare_delta_zip, TaskResourceHeader
from golem.environments.Environment import Environment
from golem.network.p2p.Node import Node
from golem.core.compress import decompress

from examples.gnr.RenderingDirManager import getTmpPath

import os
import logging
import time
import pickle

logger = logging.getLogger(__name__)

##############################################
def checkSubtask_idWrapper(func):
    def checkSubtask_id(*args, **kwargs):
        task = args[0]
        subtask_id = args[1]
        if subtask_id not in task.subTasksGiven:
            logger.error("This is not my subtask {}".format(subtask_id))
            return False
        return func(*args, **kwargs)
    return checkSubtask_id

##############################################
class GNRTaskBuilder(TaskBuilder):
    #######################
    def __init__(self, client_id, taskDefinition, root_path):
        self.taskDefinition = taskDefinition
        self.client_id       = client_id
        self.root_path       = root_path

    #######################
    def build(self):
        pass

##############################################
class GNRSubtask():
    #######################
    def __init__(self, subtask_id, startChunk, endChunk):
        self.subtask_id = subtask_id
        self.startChunk = startChunk
        self.endChunk = endChunk

##############################################
class GNROptions:
    #######################
    def __init__(self):
        self.environment = Environment()

    #######################
    def addToResources(self, resources):
        return resources

    #######################
    def removeFromResources(self, resources):
        return resources

##############################################
class GNRTask(Task):
    #####################
    def __init__(self, src_code, client_id, task_id, owner_address, owner_port, ownerKeyId, environment,
                  ttl, subtaskTtl, resource_size, estimated_memory):
        th = TaskHeader(client_id, task_id, owner_address, owner_port, ownerKeyId, environment, Node(),
                         ttl, subtaskTtl, resource_size, estimated_memory)
        Task.__init__(self, th, src_code)

        self.taskResources = []

        self.total_tasks = 0
        self.lastTask = 0

        self.num_tasks_received = 0
        self.subTasksGiven = {}
        self.numFailedSubtasks = 0

        self.full_task_timeout = 2200
        self.counting_nodes = {}

        self.res_files = {}

    #######################
    def initialize(self):
        pass

    #######################
    def restart (self):
        self.num_tasks_received = 0
        self.lastTask = 0
        self.subTasksGiven.clear()

        self.numFailedSubtasks = 0
        self.header.last_checking = time.time()
        self.header.ttl = self.full_task_timeout


    #######################
    def get_chunks_left(self):
        return (self.total_tasks - self.lastTask) + self.numFailedSubtasks

    #######################
    def get_progress(self):
        return float(self.lastTask) / self.total_tasks


    #######################
    def needs_computation(self):
        return (self.lastTask != self.total_tasks) or (self.numFailedSubtasks > 0)

    #######################
    def finishedComputation(self):
        return self.num_tasks_received == self.total_tasks

    #######################
    def computation_started(self, extra_data):
        pass

    #######################
    def computation_failed(self, subtask_id):
        self._markSubtaskFailed(subtask_id)

    #######################
    def get_total_tasks(self):
        return self.total_tasks

    #######################
    def get_total_chunks(self):
        return self.total_tasks

    #######################
    def get_active_tasks(self):
        return self.lastTask

    #######################
    def get_active_chunks(self):
        return self.lastTask

    #######################
    def setResFiles(self, res_files):
        self.res_files = res_files

    #######################
    def prepare_resource_delta(self, task_id, resource_header):
        if task_id == self.header.task_id:
            commonPathPrefix, dir_name, tmp_dir = self.__get_taskDirParams()

            if not os.path.exists(tmp_dir):
                os.makedirs(tmp_dir)

            if os.path.exists(dir_name):
                return prepare_delta_zip(dir_name, resource_header, tmp_dir, self.taskResources)
            else:
                return None
        else:
            return None

    #######################
    def get_resource_parts_list(self, task_id, resource_header):
        if task_id == self.header.task_id:
            commonPathPrefix, dir_name, tmp_dir = self.__get_taskDirParams()

            if os.path.exists(dir_name):
                delta_header, parts = TaskResourceHeader.build_parts_header_delta_from_chosen(resource_header, dir_name, self.res_files)
                return delta_header, parts
            else:
                return None
        else:
            return None

    #######################
    def __get_taskDirParams(self):
        commonPathPrefix = os.path.commonprefix(self.taskResources)
        commonPathPrefix = os.path.dirname(commonPathPrefix)
        dir_name = commonPathPrefix #os.path.join("res", self.header.client_id, self.header.task_id, "resources")
        tmp_dir = getTmpPath(self.header.client_id, self.header.task_id, self.root_path)
        if not os.path.exists(tmp_dir):
                os.makedirs(tmp_dir)

        return commonPathPrefix, dir_name, tmp_dir

    #######################
    def abort (self):
        pass

    #######################
    def update_task_state(self, task_state):
        pass

    #######################
    def load_taskResults(self, task_result, result_type, tmp_dir):
        if result_type == result_types['data']:
            return  [ self._unpackTaskResult(trp, tmp_dir) for trp in task_result ]
        elif result_type == result_types['files']:
            return task_result
        else:
            logger.error("Task result type not supported {}".format(result_type))
            return []

    #######################
    @checkSubtask_idWrapper
    def verify_subtask(self, subtask_id):
       return self.subTasksGiven[ subtask_id ]['status'] == SubtaskStatus.finished

    #######################
    def verify_task(self):
        return self.finishedComputation()

    #######################
    @checkSubtask_idWrapper
    def get_price_mod(self, subtask_id):
        return 1

    #######################
    @checkSubtask_idWrapper
    def get_trust_mod(self, subtask_id):
        return 1.0

    #######################
    @checkSubtask_idWrapper
    def restart_subtask(self, subtask_id):
        if subtask_id in self.subTasksGiven:
            if self.subTasksGiven[ subtask_id ][ 'status' ] == SubtaskStatus.starting:
                self._markSubtaskFailed(subtask_id)
            elif self.subTasksGiven[ subtask_id ][ 'status' ] == SubtaskStatus.finished :
                self._markSubtaskFailed(subtask_id)
                tasks = self.subTasksGiven[ subtask_id ]['end_task'] - self.subTasksGiven[ subtask_id  ]['start_task'] + 1
                self.num_tasks_received -= tasks

    #######################
    @checkSubtask_idWrapper
    def shouldAccept(self, subtask_id):
        if self.subTasksGiven[ subtask_id ][ 'status' ] != SubtaskStatus.starting:
            return False
        return True

    #######################
    @checkSubtask_idWrapper
    def _markSubtaskFailed(self, subtask_id):
        self.subTasksGiven[ subtask_id ]['status'] = SubtaskStatus.failure
        self.counting_nodes[ self.subTasksGiven[ subtask_id ][ 'client_id' ] ] = -1
        self.numFailedSubtasks += 1

    #######################
    def _unpackTaskResult(self, trp, tmp_dir):
        tr = pickle.loads(trp)
        with open(os.path.join(tmp_dir, tr[ 0 ]), "wb") as fh:
            fh.write(decompress(tr[ 1 ]))
        return os.path.join(tmp_dir, tr[0])
