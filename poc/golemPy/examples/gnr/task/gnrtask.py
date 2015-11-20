from golem.task.TaskBase import Task, TaskHeader, TaskBuilder, result_types
from golem.task.TaskState import SubtaskStatus
from golem.resource.Resource import prepare_delta_zip, TaskResourceHeader
from golem.environments.Environment import Environment
from golem.network.p2p.Node import Node
from golem.core.compress import decompress

from examples.gnr.RenderingDirManager import get_tmp_path

import os
import logging
import time
import pickle

logger = logging.getLogger(__name__)

##############################################
def check_subtask_id_wrapper(func):
    def check_subtask_id(*args, **kwargs):
        task = args[0]
        subtask_id = args[1]
        if subtask_id not in task.subtasks_given:
            logger.error("This is not my subtask {}".format(subtask_id))
            return False
        return func(*args, **kwargs)
    return check_subtask_id

##############################################
class GNRTaskBuilder(TaskBuilder):
    #######################
    def __init__(self, client_id, task_definition, root_path):
        self.task_definition = task_definition
        self.client_id       = client_id
        self.root_path       = root_path

    #######################
    def build(self):
        pass

##############################################
class GNRSubtask():
    #######################
    def __init__(self, subtask_id, start_chunk, end_chunk):
        self.subtask_id = subtask_id
        self.start_chunk = start_chunk
        self.end_chunk = end_chunk

##############################################
class GNROptions:
    #######################
    def __init__(self):
        self.environment = Environment()

    #######################
    def add_to_resources(self, resources):
        return resources

    #######################
    def remove_from_resources(self, resources):
        return resources

##############################################
class GNRTask(Task):
    #####################
    def __init__(self, src_code, client_id, task_id, owner_address, owner_port, owner_key_id, environment,
                  ttl, subtask_ttl, resource_size, estimated_memory):
        th = TaskHeader(client_id, task_id, owner_address, owner_port, owner_key_id, environment, Node(),
                         ttl, subtask_ttl, resource_size, estimated_memory)
        Task.__init__(self, th, src_code)

        self.task_resources = []

        self.total_tasks = 0
        self.last_task = 0

        self.num_tasks_received = 0
        self.subtasks_given = {}
        self.num_failed_subtasks = 0

        self.full_task_timeout = 2200
        self.counting_nodes = {}

        self.res_files = {}

    #######################
    def initialize(self):
        pass

    #######################
    def restart (self):
        self.num_tasks_received = 0
        self.last_task = 0
        self.subtasks_given.clear()

        self.num_failed_subtasks = 0
        self.header.last_checking = time.time()
        self.header.ttl = self.full_task_timeout


    #######################
    def get_chunks_left(self):
        return (self.total_tasks - self.last_task) + self.num_failed_subtasks

    #######################
    def get_progress(self):
        return float(self.last_task) / self.total_tasks


    #######################
    def needs_computation(self):
        return (self.last_task != self.total_tasks) or (self.num_failed_subtasks > 0)

    #######################
    def finished_computation(self):
        return self.num_tasks_received == self.total_tasks

    #######################
    def computation_started(self, extra_data):
        pass

    #######################
    def computation_failed(self, subtask_id):
        self._mark_subtask_failed(subtask_id)

    #######################
    def get_total_tasks(self):
        return self.total_tasks

    #######################
    def get_total_chunks(self):
        return self.total_tasks

    #######################
    def get_active_tasks(self):
        return self.last_task

    #######################
    def get_active_chunks(self):
        return self.last_task

    #######################
    def set_res_files(self, res_files):
        self.res_files = res_files

    #######################
    def prepare_resource_delta(self, task_id, resource_header):
        if task_id == self.header.task_id:
            common_path_prefix, dir_name, tmp_dir = self.__get_task_dir_params()

            if not os.path.exists(tmp_dir):
                os.makedirs(tmp_dir)

            if os.path.exists(dir_name):
                return prepare_delta_zip(dir_name, resource_header, tmp_dir, self.task_resources)
            else:
                return None
        else:
            return None

    #######################
    def get_resource_parts_list(self, task_id, resource_header):
        if task_id == self.header.task_id:
            common_path_prefix, dir_name, tmp_dir = self.__get_task_dir_params()

            if os.path.exists(dir_name):
                delta_header, parts = TaskResourceHeader.build_parts_header_delta_from_chosen(resource_header, dir_name, self.res_files)
                return delta_header, parts
            else:
                return None
        else:
            return None

    #######################
    def __get_task_dir_params(self):
        common_path_prefix = os.path.commonprefix(self.task_resources)
        common_path_prefix = os.path.dirname(common_path_prefix)
        dir_name = common_path_prefix #os.path.join("res", self.header.client_id, self.header.task_id, "resources")
        tmp_dir = get_tmp_path(self.header.client_id, self.header.task_id, self.root_path)
        if not os.path.exists(tmp_dir):
                os.makedirs(tmp_dir)

        return common_path_prefix, dir_name, tmp_dir

    #######################
    def abort (self):
        pass

    #######################
    def update_task_state(self, task_state):
        pass

    #######################
    def load_task_results(self, task_result, result_type, tmp_dir):
        if result_type == result_types['data']:
            return  [ self._unpack_task_result(trp, tmp_dir) for trp in task_result ]
        elif result_type == result_types['files']:
            return task_result
        else:
            logger.error("Task result type not supported {}".format(result_type))
            return []

    #######################
    @check_subtask_id_wrapper
    def verify_subtask(self, subtask_id):
       return self.subtasks_given[ subtask_id ]['status'] == SubtaskStatus.finished

    #######################
    def verify_task(self):
        return self.finished_computation()

    #######################
    @check_subtask_id_wrapper
    def get_price_mod(self, subtask_id):
        return 1

    #######################
    @check_subtask_id_wrapper
    def get_trust_mod(self, subtask_id):
        return 1.0

    #######################
    @check_subtask_id_wrapper
    def restart_subtask(self, subtask_id):
        if subtask_id in self.subtasks_given:
            if self.subtasks_given[ subtask_id ][ 'status' ] == SubtaskStatus.starting:
                self._mark_subtask_failed(subtask_id)
            elif self.subtasks_given[ subtask_id ][ 'status' ] == SubtaskStatus.finished :
                self._mark_subtask_failed(subtask_id)
                tasks = self.subtasks_given[ subtask_id ]['end_task'] - self.subtasks_given[ subtask_id  ]['start_task'] + 1
                self.num_tasks_received -= tasks

    #######################
    @check_subtask_id_wrapper
    def should_accept(self, subtask_id):
        if self.subtasks_given[ subtask_id ][ 'status' ] != SubtaskStatus.starting:
            return False
        return True

    #######################
    @check_subtask_id_wrapper
    def _mark_subtask_failed(self, subtask_id):
        self.subtasks_given[ subtask_id ]['status'] = SubtaskStatus.failure
        self.counting_nodes[ self.subtasks_given[ subtask_id ][ 'client_id' ] ] = -1
        self.num_failed_subtasks += 1

    #######################
    def _unpack_task_result(self, trp, tmp_dir):
        tr = pickle.loads(trp)
        with open(os.path.join(tmp_dir, tr[ 0 ]), "wb") as fh:
            fh.write(decompress(tr[ 1 ]))
        return os.path.join(tmp_dir, tr[0])
