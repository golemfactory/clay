import abc
import logging
import time
from typing import List, Type

from apps.core.task.coretaskstate import TaskDefinition, TaskDefaults, Options
import golem
from golem.core.simpleserializer import CBORSerializer, DictSerializer
from golem.network.p2p.node import Node
from golem.task.taskstate import TaskState

logger = logging.getLogger("golem.task")


class TaskTypeInfo(object):
    """ Information about task that allows to define and build a new task"""

    def __init__(self,
                 name: str,
                 definition: Type[TaskDefinition],
                 defaults: TaskDefaults,
                 options: Type[Options],
                 task_builder_type: 'Type[TaskBuilder]'):
        self.name = name
        self.defaults = defaults
        self.options = options
        self.definition = definition
        self.task_builder_type = task_builder_type


# TODO change types to enums - for now it gets
# evt.comp.task.test.status Error WAMP message serialization
# error: unsupported type: <enum 'ResultType'> undefined
# Issue #2408

class ResultType(object): # class ResultType(Enum):
    DATA = 0
    FILES = 1


class TaskHeader(object):
    """ Task header describe general information about task as an request and is propagated in the
        network as an offer for computing nodes
    """
    def __init__(self,
                 node_name: str,
                 task_id: str,
                 task_owner_address,
                 task_owner_port,
                 task_owner_key_id,
                 environment: str, # environment.get_id()
                 task_owner=None,
                 deadline=0.0,
                 subtask_timeout=0.0,
                 resource_size=0,
                 estimated_memory=0,
                 min_version=golem.__version__,
                 max_price: int=0,
                 signature=None):
        """
        :param max_price: maximum price that this (requestor) node may
        pay for an hour of computation
        :param docker_images: docker image specification
        """

        self.task_id = task_id
        self.task_owner_key_id = task_owner_key_id
        self.task_owner_address = task_owner_address
        self.task_owner_port = task_owner_port
        self.task_owner = task_owner
        # TODO change last_checking param. Issue #2407
        self.last_checking = time.time()
        self.deadline = deadline
        self.subtask_timeout = subtask_timeout
        self.node_name = node_name
        self.resource_size = resource_size
        self.environment = environment
        self.estimated_memory = estimated_memory
        self.min_version = min_version
        self.max_price = max_price
        self.signature = signature

    def __repr__(self):
        return '<Header: %r>' % (self.task_id,)

    def to_binary(self):
        return self.dict_to_binary(self.to_dict())

    def to_dict(self):
        return DictSerializer.dump(self, typed=False)

    @staticmethod
    def from_dict(dictionary):
        th = DictSerializer.load(dictionary, as_class=TaskHeader)
        th.last_checking = time.time()

        if isinstance(th.task_owner, dict):
            th.task_owner = Node.from_dict(th.task_owner)
        return th

    @classmethod
    def dict_to_binary(cls, dictionary):
        """ Nullifies the properties not required for signature verification
        and sorts the task dict representation in order to have the same
        resulting binary blob after serialization.
        """
        self_dict = dict(dictionary)
        self_dict.pop('last_checking', None)
        self_dict.pop('signature', None)

        # "port_statuses" is a nested dict and needs to be sorted;
        # Python < 3.7 does not guarantee the same dict iteration ordering
        port_statuses = self_dict['task_owner'].get('port_statuses')
        if isinstance(port_statuses, dict):
            self_dict['task_owner']['port_statuses'] = \
                cls._ordered(port_statuses)

        self_dict['task_owner'] = cls._ordered(self_dict['task_owner'])

        if self_dict.get('docker_images'):
            self_dict['docker_images'] = [cls._ordered(di) for di
                                          in self_dict['docker_images']]

        return CBORSerializer.dumps(cls._ordered(self_dict))

    @staticmethod
    def _ordered(dictionary):
        return sorted(dictionary.items())


class TaskBuilder(abc.ABC):
    def __init__(self):
        pass

    @abc.abstractmethod
    def build(self) -> 'Task':
        pass

    @classmethod
    @abc.abstractmethod
    def build_definition(cls, task_type: TaskTypeInfo, dictionary,
                         minimal=False):
        """ Build task defintion from dictionary with described options.
        :param dict dictionary: described all options need to build a task
        :param bool minimal: if this option is set too True, then only minimal
        definition that can be used for task testing can be build. Otherwise
        all necessary options must be specified in dictionary
        """
        pass


class TaskEventListener(object):
    def __init__(self):
        pass

    def notify_update_task(self, task_id):
        pass


class Task(abc.ABC):

    class ExtraData(object):
        def __init__(self, should_wait=False, ctd=None, **kwargs):
            self.should_wait = should_wait
            self.ctd = ctd

            for key, value in kwargs.items():
                setattr(self, key, value)

    # TODO why do we need that instead of calling .build() directly? issue #2409
    @classmethod
    def build_task(cls, task_builder: TaskBuilder) -> 'Task':
        if not isinstance(task_builder, TaskBuilder):
            raise TypeError("Incorrect 'task_builder' type: {}. Should be: TaskBuilder".format(type(task_builder)))
        return task_builder.build()

    def __init__(self, header: TaskHeader, src_code: str, task_definition):
        self.src_code = src_code
        self.header = header
        self.task_definition = task_definition

        self.listeners = []

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['listeners']
        return state

    def __setstate__(self, state):
        self.__dict__ = state
        self.listeners = []

    def __repr__(self):
        return '<Task: %r>' % (self.header,)

    def register_listener(self, listener):
        if not isinstance(listener, TaskEventListener):
            raise TypeError("Incorrect 'listener' type: {}. Should be: TaskEventListener".format(type(listener)))
        self.listeners.append(listener)

    def unregister_listener(self, listener):
        if listener in self.listeners:
            self.listeners.remove(listener)
        else:
            logger.warning("Trying to unregister listener that wasn't registered.")

    @abc.abstractmethod
    def initialize(self, dir_manager):
        """Called after adding a new task, may initialize or create some resources
        or do other required operations.
        :param DirManager dir_manager: DirManager instance for accessing temp dir for this task
        """
        return  # Implement in derived class

    @abc.abstractmethod
    def query_extra_data(self, perf_index: float, num_cores=1, node_id: str=None, node_name: str=None) -> ExtraData:
        """ Called when a node asks with given parameters asks for a new subtask to compute.
        :param int perf_index: performance that given node declares
        :param int num_cores: number of cores that current node declares
        :param None|str node_id: id of a node that wants to get a next subtask
        :param None|str node_name: name of a node that wants to get a next subtask
        :return ExtraData
        """
        pass  # Implement in derived class

    def create_reference_data_for_task_validation(self):
        """
        If task validation requires some reference data, then the overriding methods have to generate it.
        The reference task will be solved on local computer (by requestor) in order to obtain reference results.
        The reference results will be used to validate the output given by providers.
        :return:
        """
        pass

    @abc.abstractmethod
    def short_extra_data_repr(self, extra_data: ExtraData) -> str:
        """ Should return a short string with general task description that may be used for logging or stats gathering.
        :param extra_data:
        :return str:
        """
        pass  # Implement in derived class

    @abc.abstractmethod
    def needs_computation(self) -> bool:
        """ Return information if there are still some subtasks that may be dispended
        :return bool: True if there are still subtask that should be computed, False otherwise
        """
        pass  # Implement in derived class

    @abc.abstractmethod
    def finished_computation(self) -> bool:
        """ Return information if tasks has been fully computed
        :return bool: True if there is all tasks has been computed and verified
        """
        return False

    @abc.abstractmethod
    def computation_finished(self, subtask_id, task_result,
                             result_type=ResultType.DATA,
                             verification_finished=None):
        """ Inform about finished subtask
        :param subtask_id: finished subtask id
        :param task_result: task result, can be binary data or list of files
        :param result_type: ResultType representation
        """
        return  # Implement in derived class

    @abc.abstractmethod
    def computation_failed(self, subtask_id):
        """ Inform that computation of a task with given id has failed
        :param subtask_id:
        """
        return  # Implement in derived class

    @abc.abstractmethod
    def verify_subtask(self, subtask_id):
        """ Verify given subtask
        :param subtask_id:
        :return bool: True if a subtask passed verification, False otherwise
        """
        return  # Implement in derived class

    @abc.abstractmethod
    def verify_task(self):
        """ Verify whole task after computation
        :return bool: True if task passed verification, False otherwise
        """
        return  # Implement in derived class

    @abc.abstractmethod
    def get_total_tasks(self) -> int:
        """ Return total number of tasks that should be computed
        :return int: number should be greater than 0
        """
        pass  # Implement in derived class

    @abc.abstractmethod
    def get_active_tasks(self) -> int:
        """ Return number of tasks that are currently being computed
        :return int: number should be between 0 and a result of get_total_tasks
        """
        pass  # Implement in derived class

    @abc.abstractmethod
    def get_tasks_left(self) -> int:
        """ Return number of tasks that still should be computed
        :return int: number should be between 0 and a result of get_total_tasks
        """
        pass  # Implement in derived class

    @abc.abstractmethod
    def restart(self):
        """ Restart all subtask computation for this task """
        return  # Implement in derived class

    @abc.abstractmethod
    def restart_subtask(self, subtask_id):
        """ Restart subtask with given id """
        return  # Implement in derived class

    @abc.abstractmethod
    def abort(self):
        """ Abort task and all computations """
        return  # Implement in derived class

    @abc.abstractmethod
    def get_progress(self) -> float:
        """ Return task computations progress
        :return float: Return number between 0.0 and 1.0.
        """
        pass  # Implement in derived class

    def get_resources(self) -> list:
        """ Return list of files that are need to compute this task."""
        return []

    @abc.abstractmethod
    def update_task_state(self, task_state: TaskState):
        """Update some task information taking into account new state.
        :param TaskState task_state:
        """
        return  # Implement in derived class

    @abc.abstractmethod
    def get_trust_mod(self, subtask_id) -> int:
        """ Return trust modifier for given subtask. This number may be taken into account during increasing
        or decreasing trust for given node after successful or failed computation.
        :param subtask_id:
        :return int:
        """
        pass  # Implement in derived class

    @abc.abstractmethod
    def add_resources(self, resources: set):
        """ Add resources to a task
        :param resources:
        """
        return  # Implement in derived class

    def get_stdout(self, subtask_id) -> str:
        """ Return stdout received after computation of subtask_id, if there is no data available
        return empty string
        :param subtask_id:
        :return str:
        """
        return ""

    def get_stderr(self, subtask_id) -> str:
        """ Return stderr received after computation of subtask_id, if there is no data available
        return emtpy string
        :param subtask_id:
        :return str:
        """
        return ""

    def get_results(self, subtask_id) -> List:
        """ Return list of files containing results for subtask with given id
        :param subtask_id:
        :return list:
        """
        return []

    def result_incoming(self, subtask_id):
        """ Informs that a computed task result is being retrieved
        :param subtask_id:
        :return:
        """
        pass

    def get_output_names(self) -> List:
        """ Return list of files containing final import task results
        :return list:
        """
        return []

    def get_output_states(self) -> List:
        """ Return list of states of final task results
        :return list:
        """
        return []

    @abc.abstractmethod
    def copy_subtask_results(
            self, subtask_id: str, old_subtask_info: dict, results: List[str]) \
            -> None:
        """
        Copy results of a single subtask from another task
        """
        raise NotImplementedError()
