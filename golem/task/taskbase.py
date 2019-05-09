import abc
import logging
from enum import Enum
from typing import (
    List,
    Optional,
    Type,
)

import golem_messages
from golem_messages.datastructures import tasks as dt_tasks

from apps.core.task.coretaskstate import TaskDefinition, Options
from golem.task.taskstate import TaskState

logger = logging.getLogger("golem.task")


class AcceptClientVerdict(Enum):
    ACCEPTED = 0
    REJECTED = 1
    SHOULD_WAIT = 2


class TaskPurpose(Enum):
    TESTING = "testing"
    REQUESTING = "requesting"


class TaskTypeInfo(object):
    """ Information about task that allows to define and build a new task"""

    def __init__(self,
                 name: str,
                 definition: Type[TaskDefinition],
                 options: Type[Options],
                 task_builder_type: 'Type[TaskBuilder]') -> None:
        self.name = name
        self.options = options
        self.definition = definition
        self.task_builder_type = task_builder_type

    # pylint: disable=unused-argument
    def for_purpose(self, purpose: TaskPurpose) -> 'TaskTypeInfo':
        return self

    @classmethod
    # pylint:disable=unused-argument
    def get_preview(cls, task, single=False):
        pass


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

    # TODO: Backward compatibility only. The rendering tasks should
    # move to overriding their own TaskDefinitions instead of
    # overriding `build_dictionary. Issue #2424`
    @staticmethod
    def build_dictionary(definition: TaskDefinition) -> dict:
        return definition.to_dict()


class TaskEventListener(object):
    def __init__(self):
        pass

    def notify_update_task(self, task_id):
        pass


class Task(abc.ABC):

    class ExtraData(object):
        def __init__(self, ctd=None, **kwargs):
            self.ctd = ctd

            for key, value in kwargs.items():
                setattr(self, key, value)

    def __init__(self,
                 header: dt_tasks.TaskHeader,
                 task_definition: TaskDefinition) -> None:
        self.header = header
        self.task_definition = task_definition

        self.listeners = []  # type: List[TaskEventListener]

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
            raise TypeError(
                "Incorrect 'listener' type: {}. "
                "Should be: TaskEventListener".format(type(listener)))
        self.listeners.append(listener)

    def unregister_listener(self, listener):
        if listener in self.listeners:
            self.listeners.remove(listener)
        else:
            logger.warning(
                "Trying to unregister listener that wasn't registered.")

    @abc.abstractmethod
    def initialize(self, dir_manager):
        """Called after adding a new task, may initialize or create some resources
        or do other required operations.
        :param DirManager dir_manager: DirManager instance for accessing temp dir for this task
        """
        return  # Implement in derived class

    @abc.abstractmethod
    def query_extra_data(self, perf_index: float,
                         node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> 'ExtraData':
        """ Called when a node asks with given parameters asks for a new
        subtask to compute.
        :param perf_index: performance that given node declares
        :param node_id: id of a node that wants to get a next subtask
        :param node_name: name of a node that wants to get a next subtask
        """
        pass  # Implement in derived class

    @abc.abstractmethod
    def query_extra_data_for_test_task(self) -> golem_messages.message.ComputeTaskDef:  # noqa pylint:disable=line-too-long
        pass  # Implement in derived methods

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
                             verification_finished=None):
        """ Inform about finished subtask
        :param subtask_id: finished subtask id
        :param task_result: task result, can be binary data or list of files
        """
        return  # Implement in derived class

    @abc.abstractmethod
    def computation_failed(self, subtask_id: str, ban_node: bool = True):
        """ Inform that computation of a task with given id has failed
        :param subtask_id:
        :param ban_node: Whether to ban this node from this task
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

    @abc.abstractmethod
    def to_dictionary(self):
        pass

    @abc.abstractmethod
    def should_accept_client(self, node_id):
        pass

    @abc.abstractmethod
    def accept_client(self, node_id):
        pass

    # pylint: disable=unused-argument, no-self-use
    def get_finishing_subtasks(self, node_id: str) -> List[dict]:
        return []

    def external_verify_subtask(self, subtask_id, verdict):
        """
        Verify subtask results
        """
        return None
