import abc
import hashlib
import logging
import time
from typing import List, Type, Optional, Tuple, Any

from apps.core.task.coretaskstate import TaskDefinition, TaskDefaults, Options
import golem
from golem.core import common
from golem.core.common import get_timestamp_utc
from golem.core.simpleserializer import CBORSerializer, DictSerializer
from golem.network.p2p.node import Node
from golem.task.masking import Mask
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


class TaskFixedHeader(object):  # pylint: disable=too-many-instance-attributes
    """
    TaskFixedHeader is the fixed (i.e. unchangeable) part of TaskHeader
    """
    def __init__(self,  # pylint: disable=too-many-arguments
                 task_id: str,
                 environment: str,  # environment.get_id()
                 task_owner: Node,
                 deadline=0.0,
                 subtask_timeout=0.0,
                 resource_size=0,
                 estimated_memory=0,
                 min_version=golem.__version__,
                 max_price: int = 0,
                 subtasks_count: int = 0,
                 concent_enabled: bool = False) -> None:
        """
        :param max_price: maximum price that this (requestor) node may
        pay for an hour of computation
        :param docker_images: docker image specification
        """

        self.task_id = task_id
        self.task_owner = task_owner
        # TODO change last_checking param. Issue #2407
        self.last_checking = time.time()
        self.deadline = deadline
        self.subtask_timeout = subtask_timeout
        self.subtasks_count = subtasks_count
        self.resource_size = resource_size
        self.environment = environment
        self.estimated_memory = estimated_memory
        self.min_version = min_version
        self.max_price = max_price
        self.concent_enabled = concent_enabled

        self.update_checksum()

    def __repr__(self):
        return '<FixedHeader: %r>' % (self.task_id,)

    def to_binary(self):
        return self.dict_to_binary(self.to_dict())

    def to_dict(self):
        return DictSerializer.dump(self, typed=False)

    def update_checksum(self) -> None:
        self.checksum = hashlib.sha256(self.to_binary()).digest()

    @staticmethod
    def from_dict(dictionary) -> 'TaskFixedHeader':
        if 'subtasks_count' not in dictionary:
            logger.debug(
                "Subtasks count missing. Implicit 1. dictionary=%r",
                dictionary,
            )
            dictionary['subtasks_count'] = 1
        th: TaskFixedHeader = \
            DictSerializer.load(dictionary, as_class=TaskFixedHeader)
        th.last_checking = time.time()

        if isinstance(th.task_owner, dict):
            th.task_owner = Node.from_dict(th.task_owner)

        th.update_checksum()
        return th

    @classmethod
    def dict_to_binary(cls, dictionary: dict) -> bytes:
        return CBORSerializer.dumps(cls.dict_to_binarizable(dictionary))

    @classmethod
    def dict_to_binarizable(cls, dictionary: dict) -> List[tuple]:
        """ Nullifies the properties not required for signature verification
        and sorts the task dict representation in order to have the same
        resulting binary blob after serialization.
        """
        self_dict = dict(dictionary)
        self_dict.pop('last_checking', None)
        self_dict.pop('checksum', None)

        # "port_statuses" is a nested dict and needs to be sorted;
        # Python < 3.7 does not guarantee the same dict iteration ordering
        port_statuses = self_dict['task_owner'].get('port_statuses')
        if isinstance(port_statuses, dict):
            self_dict['task_owner']['port_statuses'] = \
                cls._ordered(port_statuses)

        self_dict['task_owner'] = cls._ordered(self_dict['task_owner'])

        if 'docker_images' in self_dict:
            self_dict['docker_images'] = [cls._ordered(di) for di
                                          in self_dict['docker_images']]

        return cls._ordered(self_dict)

    @staticmethod
    def validate(th_dict_repr: dict) -> None:
        """Checks if task header dict representation has correctly
           defined parameters
         :param dict th_dict_repr: task header dictionary representation
        """
        if not isinstance(th_dict_repr.get('task_id'), str):
            raise ValueError('Task ID missing')

        if not isinstance(th_dict_repr.get('task_owner'), dict):
            raise ValueError('Task owner missing')

        if not isinstance(th_dict_repr['task_owner'].get('node_name'), str):
            raise ValueError('Task owner node name missing')

        if not isinstance(th_dict_repr['deadline'], (int, float)):
            raise ValueError("Deadline is not a timestamp")

        if th_dict_repr['deadline'] < common.get_timestamp_utc():
            msg = "Deadline already passed \n " \
                  "task_id = %s \n " \
                  "node name = %s " % \
                  (th_dict_repr['task_id'],
                   th_dict_repr['task_owner']['node_name'])
            raise ValueError(msg)

        if not isinstance(th_dict_repr['subtask_timeout'], int):
            msg = "Subtask timeout is not a number \n " \
                  "task_id = %s \n " \
                  "node name = %s " % \
                  (th_dict_repr['task_id'],
                   th_dict_repr['task_owner']['node_name'])
            raise ValueError(msg)

        if th_dict_repr['subtask_timeout'] < 0:
            msg = "Subtask timeout is less than 0 \n " \
                  "task_id = %s \n " \
                  "node name = %s " % \
                  (th_dict_repr['task_id'],
                   th_dict_repr['task_owner']['node_name'])
            raise ValueError(msg)

        try:
            if th_dict_repr['subtasks_count'] < 1:
                msg = "Subtasks count is less than 1 (%r)\n" \
                      "task_id = %s \n" \
                      "node name = %s" % \
                      (th_dict_repr['subtasks_count'],
                       th_dict_repr['task_id'],
                       th_dict_repr['task_owner']['node_name'])
                raise ValueError(msg)
        except (KeyError, TypeError):
            msg = "Subtasks count is missing\n" \
                  "task_id = %s \n" \
                  "node name = %s" % \
                  (th_dict_repr['task_id'],
                   th_dict_repr['task_owner']['node_name'])
            raise ValueError(msg)

    @staticmethod
    def _ordered(dictionary: dict) -> List[tuple]:
        return sorted(dictionary.items())


class TaskHeader(object):
    """
    Task header describes general information about task as an request and
    is propagated in the network as an offer for computing nodes
    """

    def __init__(
            self,
            mask: Optional[Mask] = None,
            timestamp: Optional[float] = None,
            signature: Optional[bytes] = None,
            *args, **kwargs) -> None:

        self.fixed_header = TaskFixedHeader(*args, **kwargs)
        self.mask = mask or Mask()
        self.timestamp = timestamp or get_timestamp_utc()
        self.signature = signature

    def to_binary(self) -> bytes:
        return self.dict_to_binary(self.to_dict())

    def to_dict(self) -> dict:
        return DictSerializer.dump(self, typed=False)

    def __getattr__(self, item: str) -> Any:
        if 'fixed_header' in self.__dict__ and hasattr(self.fixed_header, item):
            return getattr(self.fixed_header, item)
        raise AttributeError('TaskHeader has no attribute %r' % item)

    @staticmethod
    def from_dict(dictionary: dict) -> 'TaskHeader':
        th: TaskHeader = DictSerializer.load(dictionary, as_class=TaskHeader)
        if isinstance(th.fixed_header, dict):
            th.fixed_header = TaskFixedHeader.from_dict(th.fixed_header)
        if isinstance(th.mask, dict):
            th.mask = Mask.from_dict(th.mask)
        return th

    @classmethod
    def dict_to_binary(cls, dictionary: dict) -> bytes:
        return CBORSerializer.dumps(cls.dict_to_binarizable(dictionary))

    @classmethod
    def dict_to_binarizable(cls, dictionary: dict) -> List[tuple]:
        self_dict = dict(dictionary)
        self_dict.pop('signature', None)

        self_dict['fixed_header'] = TaskFixedHeader.dict_to_binarizable(
            self_dict['fixed_header'])

        return cls._ordered(self_dict)

    @staticmethod
    def validate(th_dict_repr: dict) -> None:
        fixed_header = th_dict_repr.get('fixed_header')
        if fixed_header:
            return TaskFixedHeader.validate(fixed_header)
        raise ValueError('Fixed header is missing')

    @staticmethod
    def _ordered(dictionary: dict) -> List[Tuple]:
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

    @property
    def price(self) -> int:
        return self.subtask_price * self.get_total_tasks()

    @property
    def subtask_price(self):
        from golem.task import taskkeeper
        return taskkeeper.compute_subtask_value(
            self.header.max_price,
            self.header.subtask_timeout,
        )

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
    def query_extra_data(self, perf_index: float, num_cores: int = 1,
                         node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> 'ExtraData':
        """ Called when a node asks with given parameters asks for a new
        subtask to compute.
        :param perf_index: performance that given node declares
        :param num_cores: number of cores that current node declares
        :param node_id: id of a node that wants to get a next subtask
        :param node_name: name of a node that wants to get a next subtask
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
            self, subtask_id: int, old_subtask_info: dict, results: List[str]) \
            -> None:
        """
        Copy results of a single subtask from another task
        """
        raise NotImplementedError()
