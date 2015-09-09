from examples.gnr.task.GNRTask import GNRTaskBuilder, GNRTask, check_subtask_id_wrapper
from golem.environments.Environment import Environment
from golem.task.TaskBase import ComputeTaskDef
from golem.task.TaskState import SubtaskStatus

import logging
import random

logger = logging.getLogger(__name__)


class PythonGNRTaskBuilder(GNRTaskBuilder):
    #######################
    def build(self):
        with open(self.task_definition.main_program_file) as f:
            src_code = f.read()
        self.task_definition.task_resources = set()

        resource_size = 0
        for resource in self.task_definition.task_resources:
            resource_size += os.stat(resource).st_size

        return PythonGNRTask(   src_code,
                            self.client_id,
                            self.task_definition.task_id,
                            "",
                            0,
                            "",
                            Environment.get_id(),
                            self.task_definition.full_task_timeout,
                            self.task_definition.subtask_timeout,
                            resource_size,
                            0,
                            self.task_definition.total_subtasks,
                            self.root_path
                          )

class PythonGNRTask(GNRTask):
    #####################
    def __init__(self, src_code, client_id, task_id, owner_address, owner_port, owner_key_id, environment,
                  ttl, subtask_ttl, resource_size, estimated_memory, total_tasks, root_path):

        GNRTask.__init__(self, src_code, client_id, task_id,owner_address, owner_port, owner_key_id, environment, ttl, subtask_ttl,
                  resource_size, estimated_memory)

        self.total_tasks = total_tasks
        self.root_path = root_path



    def query_extra_data(self, perf_index, num_cores = 1, client_id = None):
        ctd = ComputeTaskDef()
        ctd.task_id = self.header.task_id
        hash = "{}".format(random.getrandbits(128))
        ctd.subtask_id = hash
        ctd.extra_data = { "start_task" : self.last_task,
                          "end_task": self.last_task + 1 }
        ctd.return_address = self.header.task_owner_address
        ctd.return_port = self.header.task_owner_port
        ctd.taskOnwer = self.header.task_owner
        ctd.short_description = "Golem update"
        ctd.src_code = self.src_code
        ctd.performance = perf_index
        if self.last_task + 1 <= self.total_tasks:
            self.last_task += 1

        self.subtasks_given[ hash ] = ctd.extra_data
        self.subtasks_given[ hash ][ 'status' ] = SubtaskStatus.starting
        self.subtasks_given[ hash ][ 'client_id' ] = client_id

        return ctd

    #######################
    def short_extra_data_repr(self, perf_index):
        return "Generic Python Task"

    #######################
    @check_subtask_id_wrapper
    def computation_finished(self, subtask_id, task_result, dir_manager = None, result_type = 0):
        self.subtasks_given[ subtask_id ][ 'status' ] = SubtaskStatus.finished
        self.num_tasks_received += 1

