from golem.core.simpleauth import SimpleAuth
from golem.task.taskbase import Task, TaskHeader, ComputeTaskDef, resource_types
from golem.client import start_client
from golem.network.p2p.node import Node
from golem.resource.resource import TaskResourceHeader
# from golem.resource.dirmanager import DirManager

import logging.config
import binascii
import os


class DummyTaskParameters(object):

    def __init__(self, shared_data_size, subtask_data_size, result_size, difficulty):
        """Creates a new parameters object for a dummy task
        :param int shared_data_size: size of input data shared by all subtasks in bytes
        :param int subtask_data_size: size of subtask-specific input data in bytes
        :param int result_size: size of subtask result in bytes
        :param int difficulty: computational difficulty, e.g. 0x0400 to compute
        1024 hashes on average"""
        self.shared_data_size = shared_data_size
        self.subtask_data_size = subtask_data_size
        self.result_size = result_size
        self.difficulty = difficulty


class DummyTask(Task):
    """
    :type resource_parts: dict[str,list[str]]: maps a resource file to a list of parts
    :type subtask_ids: list[str]
    :type subtask_data: dict[str,str]
    :type subtask_results: dict[str,str]
    """

    def __init__(self, client_id, task_params, num_subtasks):
        """Creates a new dummy task
        :param string client_id: client id
        :param DummyTaskParameters task_params: task parameters
        1024 hashes on average
        """
        task_id = SimpleAuth.generate_uuid().get_hex()
        owner_address = ''
        owner_port = 0
        owner_key_id = ''
        environment = 'DEFAULT'
        header = TaskHeader(client_id, task_id,
                            owner_address, owner_port, owner_key_id, environment,
                            task_owner = Node(),
                            ttl = 14400,
                            subtask_timeout = 1200,
                            resource_size = task_params.shared_data_size + task_params.subtask_data_size,
                            estimated_memory = 0)
        Task.__init__(self, header, src_code = None)

        self.task_id = task_id
        self.task_params = task_params
        self.task_resources = []
        self.resource_parts = {}

        self.shared_data_file = None
        self.total_subtasks = num_subtasks  # total number of subtasks, does not change
        self.subtask_ids = []               # len of this array is number of sent subtaskt
        self.subtask_data = {}              # len of this dict is equal to self.subtask_ids
        self.subtask_results = {}           # len of this dict is number of completed subtasks

    def initialize(self, dir_manager):
        """Create resource files for this task
        :param DirManager dir_manager: DirManager instance to access tmp/resource dirs
        """
        res_path = dir_manager.get_task_resource_dir(self.task_id)
        self.shared_data_file = os.path.join(res_path, 'shared.data')

        # write some random shared data
        with open(self.shared_data_file, 'w') as shared:
            data = binascii.b2a_hex(os.urandom(self.task_params.shared_data_size))
            shared.write(data)

        self.task_resources = [self.shared_data_file]

    def short_extra_data_repr(self, perf_index = None):
        return "dummy task " + self.task_id

    def get_total_tasks(self):
        return self.total_subtasks

    def get_tasks_left(self):
        return self.total_subtasks - len(self.subtask_results)

    def needs_computation(self):
        return len(self.subtask_data) < self.total_subtasks

    def finished_computation(self):
        return self.get_tasks_left() == 0

    def query_extra_data(self, perf_index, num_cores=1, client_id=None):
        """Returns data for the next subtask.
        :param int perf_index:
        :param int num_cores:
        :param Node | None client_id:
        :rtype: ComputeTaskDef"""
        # create new subtask_id
        import uuid
        subtask_id = uuid.uuid4().get_hex()
        self.subtask_ids.append(subtask_id)

        # create subtask-specific data
        data = binascii.b2a_hex(os.urandom(self.task_params.subtask_data_size))
        self.subtask_data[subtask_id] = data

        subtask_def = ComputeTaskDef()
        subtask_def.task_id = self.task_id
        subtask_def.subtask_id = subtask_id
        subtask_def.src_code = self.src_code
        subtask_def.extra_data = {
            'data_file': self.shared_data_file,
            'subtask_data': data,
            'difficulty': self.task_params.difficulty,
            'result_size': self.task_params.result_size,
            'result_file': 'result.' + subtask_id[0:6]
        }
        subtask_def.task_owner = self.header.task_owner
        subtask_def.environment = self.header.environment
        return subtask_def

    def verify_subtask(self, subtask_id):
        # TODO: verify that task_result size is as required
        if self.task_params.difficulty == 0:
            return True

        import hashlib
        sha = hashlib.sha256()

        with open(self.shared_data_file, 'r') as shared:
            sha.update(shared.readall())
        sha.update(self.subtask_data[subtask_id])
        sha.update(self.subtask_results[subtask_id])
        digest = sha.hexdigest()
        prefix = digest[0, self.task_params.difficulty]
        return min(prefix) == '0'

    def computation_finished(self, subtask_id, task_result, dir_manager=None, result_type=0):
        self.subtask_results[subtask_id] = task_result
        if not self.verify_subtask(subtask_id):
            # TODO
            pass

    def get_resources(self, task_id, resource_header, resource_type=0):
        if resource_type == resource_types['parts']:
            dir_name = os.path.dirname(self.shared_data_file)
            delta_header, parts = TaskResourceHeader.build_parts_header_delta_from_chosen(resource_header, dir_name,
                                                                                          self.resource_parts)
            return delta_header, parts
        return None

    def add_resources(self, resource_parts):
        """Add resources to this task
        :param map[str, list[str]] resource_parts
        """
        self.resource_parts = resource_parts


def install_reactor():
    from twisted.internet import reactor
    return reactor


config_file = os.path.join(os.path.dirname(__file__), "logging.ini")
logging.config.fileConfig(config_file, disable_existing_loggers = False)

client = start_client()
params = DummyTaskParameters(1024, 2048, 256, 2)
task = DummyTask(client.get_id(), params, 3)
client.enqueue_new_task(task)

reactor = install_reactor()
reactor.run()
