from golem.core.simpleauth import SimpleAuth
from golem.task.taskbase import Task, TaskHeader
from golem.client import start_client, Client
from golem.network.p2p.node import Node
# from golem.resource.dirmanager import DirManager

import logging.config
import os

class DummyTaskParameters(object):

    def __init__(self, shared_data_size, subtask_data_size, result_size, difficulty):
        """Creates a new parameters object for a dummy task
        :param int shared_data_size: size of input data shared by all subtasks in bytes
        :param int subtask_data_Size: size of subtask-specific input data in bytes
        :param int result_size: size of subtask result in bytes
        :param int difficulty: computational difficulty, e.g. 0x0400 to compute
        1024 hashes on average"""
        self.shared_data_size = shared_data_size
        self.subtask_data_size = subtask_data_size
        self.result_size = result_size
        self.difficulty = difficulty


class DummyTask(Task):

    def __init__(self, client_id, task_params, num_subtasks):
        """Creates a new dummy task
        :param string client_id: client id
        :param DummyTaskParameters task_params: task parameters
        1024 hashes on average"""
        task_id = SimpleAuth.generate_uuid().get_hex()
        owner_address = ''
        owner_port = 0
        owner_key_id = ''
        environment = 'Dummy'
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

        self.shared_data_file = None
        self.total_subtasks = num_subtasks      # total number of subtasks, does not change
        self.remaining_subtasks = num_subtasks  # subtasks remaining to be sent
        self.completed_subtasks = 0             # subtasks for which results are delivered


    def initialize(self, dir_manager):
        """Create resource files for this task
        :param DirManager dir_manager: DirManager instance to access tmp/resource dirs
        """
        res_path = dir_manager.get_task_resource_dir(self.task_id)
        self.shared_data_file = os.path.join(res_path, 'shared.data')

        # write some random shared data
        with open(self.shared_data_file, 'w') as shared:
            import binascii
            hex = binascii.b2a_hex(os.urandom(self.task_params.shared_data_size))
            shared.write(hex)

        self.task_resources = [self.shared_data_file]

    def short_extra_data_repr(self, perf_index = None):
        return "dummy task " + self.task_id

    def get_total_tasks(self):
        return self.total_subtasks

    def get_tasks_left(self):
        return self.total_subtasks - self.completed_subtasks

    def needs_computation(self):
        return self.remaining_subtasks > 0

    def finished_computation(self):
        return self.completed_subtasks = self.total_subtasks

def install_reactor():
    #try:
    #    import qt4reactor
    #except ImportError:
    #    # Maybe qt4reactor is placed inside twisted.internet in site-packages?
    #    from twisted.internet import qt4reactor
    #qt4reactor.install()
    from twisted.internet import reactor
    return reactor


config_file = os.path.join(os.path.dirname(__file__), "logging.ini")
logging.config.fileConfig(config_file, disable_existing_loggers = False)

client = start_client()
params = DummyTaskParameters(1024, 2048, 256, 0x100)
task = DummyTask(client.get_id(), params, 3)
client.enqueue_new_task(task)

reactor = install_reactor()
reactor.run()


