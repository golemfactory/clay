from golem.environments.Environment import Environment
from golem.task.TaskBase import ComputeTaskDef
from golem.task.TaskState import SubtaskStatus

from GNRTask import GNRTask, GNRTaskBuilder

import random
import logging
import os

logger = logging.getLogger(__name__)

##############################################
class UpdateOtherGolemsTaskDefinition:
    def __init__(self):
        self.task_id = ""

        self.full_task_timeout    = 0
        self.subtask_timeout     = 0

        self.resource_dir        = ""
        self.src_file            = ""
        self.resources          = []
        self.totalSubtasks      = 1

##############################################
class UpdateOtherGolemsTaskBuilder(GNRTaskBuilder):
    #######################
    def __init__(self, client_id, taskDefinition, root_path, srcDir):
        GNRTaskBuilder.__init__(self, client_id, taskDefinition, root_path)
        self.srcDir = srcDir

    def build(self):
        with open(self.taskDefinition.src_file) as f:
            src_code = f.read()
        self.taskDefinition.taskResources = set()
        for dir, dirs, files in os.walk(self.srcDir):
            for file_ in files:
                _, ext = os.path.splitext(file_)
                if ext in '.ini':
                    continue
                self.taskDefinition.taskResources.add(os.path.join(dir,file_))

        print self.taskDefinition.taskResources
        resource_size = 0
        for resource in self.taskDefinition.taskResources:
            resource_size += os.stat(resource).st_size

        return UpdateOtherGolemsTask(   src_code,
                            self.client_id,
                            self.taskDefinition.task_id,
                            "",
                            0,
                            "",
                            self.root_path,
                            Environment.get_id(),
                            self.taskDefinition.full_task_timeout,
                            self.taskDefinition.subtask_timeout,
                            self.taskDefinition.taskResources,
                            resource_size,
                            0,
                            self.taskDefinition.totalSubtasks
                          )

##############################################
class UpdateOtherGolemsTask(GNRTask):

    def __init__(self,
                  src_code,
                  client_id,
                  task_id,
                  owner_address,
                  owner_port,
                  ownerKeyId,
                  root_path,
                  environment,
                  ttl,
                  subtaskTtl,
                  resources,
                  resource_size,
                  estimated_memory,
                  total_tasks):


        GNRTask.__init__(self, src_code, client_id, task_id, owner_address, owner_port, ownerKeyId, environment,
                            ttl, subtaskTtl, resource_size, estimated_memory)

        self.total_tasks = total_tasks
        self.root_path = root_path

        self.taskResources = resources
        self.active = True
        self.updated = {}


    #######################
    def abort (self):
        self.active = False

    #######################
    def query_extra_data(self, perf_index, num_cores, client_id):

        if client_id in self.updated:
            return None

        ctd = ComputeTaskDef()
        ctd.task_id = self.header.task_id
        hash = "{}".format(random.getrandbits(128))
        ctd.subtask_id = hash
        ctd.extra_data = { "start_task" : self.lastTask,
                          "end_task": self.lastTask + 1 }
        ctd.return_address = self.header.task_owner_address
        ctd.return_port = self.header.task_owner_port
        ctd.task_owner = self.header.task_owner
        ctd.short_description = "Golem update"
        ctd.src_code = self.src_code
        ctd.performance = perf_index
        if self.lastTask + 1 <= self.total_tasks:
            self.lastTask += 1
        self.updated[ client_id ] = True

        self.subTasksGiven[ hash ] = ctd.extra_data
        self.subTasksGiven[ hash ][ 'status' ] = SubtaskStatus.starting
        self.subTasksGiven[ hash ][ 'client_id' ] = client_id

        return ctd

    #######################
    def computation_finished(self, subtask_id, task_result, dir_manager = None, result_type = 0):
        self.subTasksGiven[ subtask_id ][ 'status' ] = SubtaskStatus.finished
