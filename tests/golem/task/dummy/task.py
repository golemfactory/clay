import random
from os import path
from threading import Lock
from typing import Optional

from eth_utils import encode_hex
import faker
from golem_messages import idgenerator
from golem_messages.datastructures import p2p as dt_p2p
from golem_messages.factories.datastructures.tasks import TaskHeaderFactory
from golem_messages.message import ComputeTaskDef

import golem
from golem.appconfig import MIN_PRICE
from golem.core import common
from golem.task.taskbase import Task, AcceptClientVerdict


fake = faker.Faker()


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

    def __str__(self):
        import pprint
        return pprint.pformat(self.__dict__)


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
        owner_address = fake.ipv4()
        owner_port = fake.random_int(min=1, max=2**16-1)
        owner_key_id = encode_hex(public_key)[2:]
        environment = self.ENVIRONMENT_NAME
        task_owner = dt_p2p.Node(
            node_name=client_id,
            pub_addr=owner_address,
            pub_port=owner_port,
            key=owner_key_id
        )

        header = TaskHeaderFactory(
            task_id=task_id,
            task_owner=task_owner,
            environment=environment,
            deadline=common.timeout_to_deadline(14400),
            subtask_timeout=1200,
            subtasks_count=num_subtasks,
            estimated_memory=0,
            max_price=MIN_PRICE,
            min_version=golem.__version__,
            timestamp=int(common.get_timestamp_utc()),
        )

        # load the script to be run remotely from the file in the current dir
        script_path = path.join(path.dirname(__file__), 'computation.py')
        with open(script_path, 'r') as f:
            self.src_code = f.read()
            self.src_code += '\noutput = run_dummy_task(' \
                'data_file, subtask_data, difficulty, result_size, tmp_path)'

        from apps.dummy.task.dummytaskstate import DummyTaskDefinition
        from apps.dummy.task.dummytaskstate import DummyTaskDefaults
        task_definition = DummyTaskDefinition(DummyTaskDefaults())
        Task.__init__(self, header, task_definition)

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
        self._lock = Lock()
        print(
            "Task created."
            f" num_subtasks={num_subtasks}"
            f" params={params}"
        )

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

    def query_extra_data(self, perf_index: float,
                         node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> Task.ExtraData:
        """ Returns data for the next subtask. """

        # create new subtask_id
        subtask_id = idgenerator.generate_new_id_from_id(self.header.task_id)

        with self._lock:
            # assign a task
            self.assigned_nodes[node_id] = subtask_id
            self.assigned_subtasks[subtask_id] = node_id
        print(
            "Subtask assigned"
            f" subtask_id={subtask_id}"
            f" node_id={common.short_node_id(node_id)}"
        )

        # create subtask-specific data, 4 bits go for one char (hex digit)
        data = random.getrandbits(self.task_params.subtask_data_size * 4)
        self.subtask_ids.append(subtask_id)
        self.subtask_data[subtask_id] = '%x' % data

        subtask_def = ComputeTaskDef()
        subtask_def['task_id'] = self.task_id
        subtask_def['subtask_id'] = subtask_id
        subtask_def['deadline'] = common.timeout_to_deadline(5 * 60)
        subtask_def['extra_data'] = {
            'data_file': self.shared_data_file,
            'subtask_data': self.subtask_data[subtask_id],
            'difficulty': self.task_params.difficulty,
            'result_size': self.task_params.result_size,
            'result_file': 'result.' + subtask_id[0:6],
            'src_code': self.src_code,
        }

        return self.ExtraData(ctd=subtask_def)

    def verify_task(self):
        # Check if self.subtask_results contains a non None result
        # for each subtack.
        if not len(self.subtask_results) == self.subtasks_count:
            print(
                "Results vs Count: "
                f"{len(self.subtask_results)} != {self.subtasks_count}",
            )
            return False
        print(f"subtask results: {self.subtask_results}")
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
                             verification_finished=None):
        print(
            "Computation finished"
            f" subtask_id: {subtask_id}"
            f" task_result: {task_result}"
        )
        with self._lock:
            if subtask_id in self.assigned_subtasks:
                node_id = self.assigned_subtasks.pop(subtask_id, None)
                self.assigned_nodes.pop(node_id, None)

        with open(task_result[0], 'r') as f:
            self.subtask_results[subtask_id] = f.read()

        if not self.verify_subtask(subtask_id):
            self.subtask_results[subtask_id] = None
        if verification_finished is not None:
            verification_finished()

    def get_resources(self):
        return self.task_resources

    def add_resources(self, resource_parts):
        """Add resources to this task.
        :param map[str, list[str]] resource_parts:
        """
        self.resource_parts = resource_parts

    def computation_failed(self, subtask_id: str, ban_node: bool = True):
        print('DummyTask.computation_failed called')
        self.computation_finished(subtask_id, None)

    def restart(self):
        print('DummyTask.restart called')

    def restart_subtask(self, subtask_id):
        print('DummyTask.restart_subtask called')

    def abort(self):
        print('DummyTask.abort called')

    def update_task_state(self, task_state):
        print(
            'DummyTask.update_task_state called'
            f" task_state={task_state}"
        )

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

    def get_finishing_subtasks(self, node_id):
        try:
            return [{'subtask_id': self.assigned_nodes[node_id]}]
        except KeyError:
            return []

    def accept_client(self, node_id):
        print(
            "DummyTask.accept_client called"
            f" node_id={common.short_node_id(node_id)}"
        )
        return
