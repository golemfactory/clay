import random
import uuid
from os import path
from threading import Lock

from golem.appconfig import MIN_PRICE
from golem.core.common import timeout_to_deadline
from golem.core.simpleauth import SimpleAuth
from golem.network.p2p.node import Node
from golem.task.taskbase import Task, TaskHeader, ComputeTaskDef


class DummyTaskParameters(object):
    """A parameter object for a dummy task.
    The difficulty is a 4 byte int; 0x00000001 is the greatest and 0xffffffff
    the least difficulty. For example difficulty = 0x003fffff requires
    0xffffffff / 0x003fffff = 1024 hash computations on average.

    :type shared_data_size: int: size of data shared by all subtasks in bytes
    :type subtask_data_size: int: size of subtask-specific data in bytes
    :type result_size: int: size of subtask result in bytes
    :type difficulty: int: computational difficulty
    """
    def __init__(self, shared_data_size, subtask_data_size, result_size,
                 difficulty):
        """
        :param int shared_data_size:
        :param int subtask_data_size:
        :param int result_size:
        :param int difficulty:
        """
        self.shared_data_size = shared_data_size
        self.subtask_data_size = subtask_data_size
        self.result_size = result_size
        self.difficulty = difficulty


class DummyTask(Task):
    """
    :type resource_parts: dict[str,list[str]]: maps a resource file
    to a list of parts
    :type subtask_ids: list[str]: length of this list is the number of subtasks
    sent for computation
    :type subtask_data: dict[str,str]
    :type subtask_results: dict[str,str]: None is stored if subtask result
    did not pass verification
    """

    ENVIRONMENT_NAME = "DUMMY"

    def __init__(self, client_id, params, num_subtasks):
        """Creates a new dummy task
        :param string client_id: client id
        :param DummyTaskParameters params: task parameters
        1024 hashes on average
        """
        task_id = SimpleAuth.generate_uuid().get_hex()
        owner_address = ''
        owner_port = 0
        owner_key_id = ''
        environment = self.ENVIRONMENT_NAME
        header = TaskHeader(
            client_id, task_id,
            owner_address, owner_port, owner_key_id, environment,
            task_owner=Node(),
            deadline=timeout_to_deadline(14400),
            subtask_timeout=1200,
            resource_size=params.shared_data_size + params.subtask_data_size,
            estimated_memory=0,
            max_price=MIN_PRICE)

        # load the script to be run remotely from the file in the current dir
        script_path = path.join(path.dirname(__file__), 'computation.py')
        with open(script_path, 'r') as f:
            src_code = f.read()
            src_code += '\noutput = run_dummy_task(' \
                        'data_file, subtask_data, difficulty, result_size)'

        Task.__init__(self, header, src_code)

        self.task_id = task_id
        self.task_params = params
        self.task_resources = []
        self.resource_parts = {}

        self.shared_data_file = None
        self.total_subtasks = num_subtasks
        self.subtask_ids = []
        self.subtask_data = {}
        self.subtask_results = {}
        self.assigned_nodes = {}
        self.assigned_subtasks = {}
        self._lock = Lock()

    def __setstate__(self, state):
        super(DummyTask, self).__setstate__(state)
        self._lock = Lock()

    def __getstate__(self):
        state = super(DummyTask, self).__getstate__()
        del state['_lock']
        return state

    def initialize(self, dir_manager):
        """Create resource files for this task
        :param DirManager dir_manager: DirManager instance to access tmp and
        resource dirs
        """
        res_path = dir_manager.get_task_resource_dir(self.task_id)
        self.shared_data_file = path.join(res_path, 'shared.data')

        # write some random shared data, 4 bits for one char
        with open(self.shared_data_file, 'w') as shared:
            num_bits = self.task_params.shared_data_size * 4
            r = random.getrandbits(num_bits - 1) + (1 << (num_bits - 1))
            data = '%x' % r
            assert len(data) == self.task_params.shared_data_size
            shared.write(data)

        self.task_resources = [self.shared_data_file]

    def short_extra_data_repr(self, perf_index=None):
        return "dummy task " + self.task_id

    def get_total_tasks(self):
        return self.total_subtasks

    def get_tasks_left(self):
        return self.total_subtasks - len(self.subtask_results)

    def needs_computation(self):
        return len(self.subtask_data) < self.total_subtasks

    def finished_computation(self):
        return self.get_tasks_left() == 0

    def query_extra_data(self, perf_index, num_cores=1, node_id=None, node_name=None):
        """Returns data for the next subtask.
        :param int perf_index:
        :param int num_cores:
        :param str | None node_id:
        :param str | None node_name:
        :rtype: ComputeTaskDef"""

        # create new subtask_id
        subtask_id = uuid.uuid4().get_hex()

        with self._lock:
            # check if a task has been assigned to this node
            if node_id in self.assigned_nodes:
                return self.ExtraData(should_wait=True)
            # assign a task
            self.assigned_nodes[node_id] = subtask_id
            self.assigned_subtasks[subtask_id] = node_id

        # create subtask-specific data, 4 bits go for one char (hex digit)
        data = random.getrandbits(self.task_params.subtask_data_size * 4)
        self.subtask_ids.append(subtask_id)
        self.subtask_data[subtask_id] = '%x' % data

        subtask_def = ComputeTaskDef()
        subtask_def.task_id = self.task_id
        subtask_def.subtask_id = subtask_id
        subtask_def.src_code = self.src_code
        subtask_def.task_owner = self.header.task_owner
        subtask_def.environment = self.header.environment
        subtask_def.return_address = self.header.task_owner_address
        subtask_def.return_port = self.header.task_owner_port
        subtask_def.deadline = timeout_to_deadline(5 * 60)
        subtask_def.extra_data = {
            'data_file': self.shared_data_file,
            'subtask_data': self.subtask_data[subtask_id],
            'difficulty': self.task_params.difficulty,
            'result_size': self.task_params.result_size,
            'result_file': 'result.' + subtask_id[0:6]
        }

        return self.ExtraData(ctd=subtask_def)

    def verify_task(self):
        # Check if self.subtask_results contains a non None result
        # for each subtack.
        if not len(self.subtask_results) == self.total_subtasks:
            return False
        return all(self.subtask_results.values())

    def verify_subtask(self, subtask_id):
        result = self.subtask_results[subtask_id]

        if len(result) != self.task_params.result_size:
            return False

        if self.task_params.difficulty == 0:
            return True

        import computation
        with open(self.shared_data_file, 'r') as f:
            input_data = f.read()

        input_data += self.subtask_data[subtask_id]
        return computation.check_pow(long(result, 16), input_data,
                                     self.task_params.difficulty)

    def computation_finished(self, subtask_id, task_result, result_type=0):
        with self._lock:
            if subtask_id in self.assigned_subtasks:
                node_id = self.assigned_subtasks.pop(subtask_id, None)
                self.assigned_nodes.pop(node_id, None)

        self.subtask_results[subtask_id] = task_result
        if not self.verify_subtask(subtask_id):
            self.subtask_results[subtask_id] = None

    def get_resources(self, resource_header, resource_type=0, tmp_dir=None):
        return self.task_resources

    def add_resources(self, resource_parts):
        """Add resources to this task.
        :param map[str, list[str]] resource_parts:
        """
        self.resource_parts = resource_parts
