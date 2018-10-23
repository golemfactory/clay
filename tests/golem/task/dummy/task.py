import random
from os import path
from threading import Lock
from typing import Optional

from eth_utils import encode_hex
from golem_messages import idgenerator
from golem_messages.message import ComputeTaskDef

from golem.appconfig import MIN_PRICE
from golem.core.common import timeout_to_deadline
from golem.network.p2p.node import Node
from golem.task.taskbase import Task, TaskHeader, ResultType,\
     AcceptClientVerdict


class DummyTaskParameters(object):
    """A parameter object for a dummy task.
    The difficulty is a 4 byte int; 0x00000001 is the greatest and 0xffffffff
    the least difficulty. For example difficulty = 0x003fffff requires
    0xffffffff / 0x003fffff = 1024 hash computations on average.

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


# pylint: disable=too-many-locals
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

    def __init__(self, client_id, params, num_subtasks, public_key):
        """Creates a new dummy task
        :param string client_id: client id
        :param DummyTaskParameters params: task parameters
        1024 hashes on average
        """
        task_id = idgenerator.generate_id(public_key)
        owner_address = ''
        owner_port = 0
        owner_key_id = encode_hex(public_key)[2:]
        environment = self.ENVIRONMENT_NAME
        header = TaskHeader(
            task_id=task_id,
            environment=environment,
            task_owner=Node(
                node_name=client_id,
                pub_addr=owner_address,
                pub_port=owner_port,
                key=owner_key_id
            ),
            deadline=timeout_to_deadline(14400),
            subtask_timeout=1200,
            subtasks_count=num_subtasks,
            resource_size=params.shared_data_size + params.subtask_data_size,
            estimated_memory=0,
            max_price=MIN_PRICE)

        # load the script to be run remotely from the file in the current dir
        script_path = path.join(path.dirname(__file__), 'computation.py')
        with open(script_path, 'r') as f:
            src_code = f.read()
            src_code += '\noutput = run_dummy_task(' \
                        'data_file, subtask_data, difficulty, result_size)'

        from apps.dummy.task.dummytaskstate import DummyTaskDefinition
        from apps.dummy.task.dummytaskstate import DummyTaskDefaults
        task_definition = DummyTaskDefinition(DummyTaskDefaults())
        Task.__init__(self, header, src_code, task_definition)

        self.task_id = task_id
        self.task_params = params
        self.task_resources = []
        self.resource_parts = {}

        self.shared_data_file = None
        self.subtasks_count = num_subtasks
        self.total_tasks = self.subtasks_count
        self.subtask_ids = []
        self.subtask_data = {}
        self.subtask_results = {}
        self.assigned_nodes = {}
        self.assigned_subtasks = {}
        self.total_tasks = 1
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

    def short_extra_data_repr(self, extra_data):
        return "dummy task " + self.task_id

    def get_trust_mod(self, subtask_id):
        return 0.

    def get_total_tasks(self):
        return self.subtasks_count

    def get_tasks_left(self):
        return self.subtasks_count - len(self.subtask_results)

    @property
    def price(self) -> int:
        return self.subtask_price * self.total_tasks

    def needs_computation(self):
        return len(self.subtask_data) < self.subtasks_count

    def finished_computation(self):
        return self.get_tasks_left() == 0

    def query_extra_data(self, perf_index: float, num_cores: int = 1,
                         node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> Task.ExtraData:
        """ Returns data for the next subtask. """

        # create new subtask_id
        subtask_id = idgenerator.generate_new_id_from_id(self.header.task_id)

        with self._lock:
            # assign a task
            self.assigned_nodes[node_id] = subtask_id
            self.assigned_subtasks[subtask_id] = node_id

        # create subtask-specific data, 4 bits go for one char (hex digit)
        data = random.getrandbits(self.task_params.subtask_data_size * 4)
        self.subtask_ids.append(subtask_id)
        self.subtask_data[subtask_id] = '%x' % data

        subtask_def = ComputeTaskDef(
            task_type='Blender',
            meta_parameters={
                'resolution': [1, 1],
                'borders_x': [0.0, 0.0],
                'borders_y': [0.0, 0.0],
                'use_compositing': False,
                'samples': 1,
                'frames': [1],
                'output_format': 'PNG',
            }
        )
        subtask_def['task_id'] = self.task_id
        subtask_def['subtask_id'] = subtask_id
        subtask_def['src_code'] = self.src_code
        subtask_def['deadline'] = timeout_to_deadline(5 * 60)
        subtask_def['extra_data'] = {
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
        if not len(self.subtask_results) == self.subtasks_count:
            return False
        return all(self.subtask_results.values())

    def verify_subtask(self, subtask_id):
        result = self.subtask_results[subtask_id]

        if not result or len(result) != self.task_params.result_size:
            return False

        if self.task_params.difficulty == 0:
            return True

        with open(self.shared_data_file, 'r') as f:
            input_data = f.read()

        input_data += self.subtask_data[subtask_id]
        from tests.golem.task.dummy import computation
        return computation.check_pow(int(result, 16), input_data,
                                     self.task_params.difficulty)

    def computation_finished(self, subtask_id, task_result,
                             result_type=ResultType.DATA,
                             verification_finished=None):
        with self._lock:
            if subtask_id in self.assigned_subtasks:
                node_id = self.assigned_subtasks.pop(subtask_id, None)
                self.assigned_nodes.pop(node_id, None)

        self.subtask_results[subtask_id] = task_result
        if not self.verify_subtask(subtask_id):
            self.subtask_results[subtask_id] = None

    def get_resources(self):
        return self.task_resources

    def add_resources(self, resource_parts):
        """Add resources to this task.
        :param map[str, list[str]] resource_parts:
        """
        self.resource_parts = resource_parts

    def computation_failed(self, subtask_id):
        print('DummyTask.computation_failed called')
        self.computation_finished(subtask_id, None)

    def restart(self):
        print('DummyTask.restart called')

    def restart_subtask(self, subtask_id):
        print('DummyTask.restart_subtask called')

    def abort(self):
        print('DummyTask.abort called')

    def update_task_state(self, task_state):
        print('DummyTask.update_task_state called')

    def get_active_tasks(self):
        return self.assigned_subtasks

    def get_progress(self):
        return 0

    def to_dictionary(self):
        return {
            'task_id': self.task_id,
            'task_params': self.task_params.__dict__
        }

    def copy_subtask_results(self, subtask_id, old_subtask_info, results):
        print('DummyTask.copy_subtask_results called')

    def query_extra_data_for_test_task(self):
        pass

    def should_accept_client(self, node_id):
        if node_id in self.assigned_nodes:
            return AcceptClientVerdict.SHOULD_WAIT
        return AcceptClientVerdict.ACCEPTED

    def accept_client(self, node_id):
        print('DummyTask.accept_client called node_id=%r '
              '- WIP: move more responsibilities from query_extra_data',
              node_id)
        return
