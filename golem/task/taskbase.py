import time
import abc
import warnings
import rlp
from rlp import sedes
warnings.simplefilter("always")
from golem.network.p2p.node import Node


class TaskHeader(rlp.Serializable):
    fields = (
        ('client_id', sedes.binary),
        ('task_id', sedes.big_endian_int),
        ('environment', sedes.binary),
        ('task_owner', Node),
        ('ttl', sedes.big_endian_int),
        ('subtask_timeout', sedes.big_endian_int),
        ('resource_size', sedes.big_endian_int),
        ('estimated_memory', sedes.big_endian_int),
        ('min_version', sedes.big_endian_int)
    )

    def __init__(self, client_id, task_id, task_owner_address=None,
                 task_owner_port=None, task_owner_key_id=None, environment=None,
                 task_owner=Node(), ttl=0, subtask_timeout=0, resource_size=0,
                 estimated_memory=0, min_version=1):
        assert isinstance(task_id, (int, long))
        assert isinstance(task_owner, Node)
        assert isinstance(ttl, (int, long))
        assert isinstance(subtask_timeout, (int, long))
        assert isinstance(min_version, (int, long))

        super(TaskHeader, self).__init__(client_id, task_id, environment,
                                         task_owner, ttl, subtask_timeout,
                                         resource_size, estimated_memory,
                                         min_version)

        if task_owner_key_id is not None:
            self.task_owner.key = task_owner_key_id
        if task_owner_address is not None:
            self.task_owner.pub_addr = task_owner_address
        if task_owner_port is not None:
            self.task_owner.pub_port = task_owner_port

        self.last_checking = time.time()

    @property
    def task_owner_address(self):
        warnings.warn("task_owner_address property is deprecated, "
                      "use task_owner.pub_addr", DeprecationWarning)
        return self.task_owner.pub_addr

    @task_owner_address.setter
    def task_owner_address(self, value):
        warnings.warn("task_owner_address property is deprecated, "
                      "use task_owner.pub_addr", DeprecationWarning)
        self.task_owner.pub_addr = value

    @property
    def task_owner_port(self):
        warnings.warn("task_owner_port property is deprecated, "
                      "use task_owner.pub_port", DeprecationWarning)
        return self.task_owner.pub_port

    @task_owner_port.setter
    def task_owner_port(self, value):
        warnings.warn("task_owner_port property is deprecated, "
                      "use task_owner.pub_port", DeprecationWarning)
        self.task_owner.pub_port = value

    @property
    def task_owner_key_id(self):
        warnings.warn("task_owner_key_id property is deprecated, "
                      "use task_owner.key", DeprecationWarning)
        return self.task_owner.key

    @task_owner_key_id.setter
    def task_owner_key_id(self, value):
        warnings.warn("task_owner_key_id property is deprecated, "
                      "use task_owner.key", DeprecationWarning)
        self.task_owner.key = value


class TaskBuilder:
    def __init__(self):
        pass

    @abc.abstractmethod
    def build(self):
        return


class ComputeTaskDef(object):
    def __init__(self):
        self.task_id = ""
        self.subtask_id = ""
        self.src_code = ""
        self.extra_data = {}
        self.short_description = ""
        self.return_address = ""
        self.return_port = 0
        self.task_owner = None
        self.key_id = 0
        self.working_directory = ""
        self.performance = 0.0
        self.environment = ""


class Task:

    @classmethod
    def build_task(cls, task_builder):
        assert isinstance(task_builder, TaskBuilder)
        return task_builder.build()

    def __init__(self, header, src_code):
        self.src_code = src_code
        self.header = header

    @abc.abstractmethod
    def initialize(self):
        """ Called after adding a new task, may initialize or create some resources or do other required operations. """
        return  # Implement in derived class

    @abc.abstractmethod
    def query_extra_data(self, perf_index, num_cores=1, client_id=None):
        """ Called when a node asks with given parameters asks for a new subtask to compute.
        :param int perf_index: performance that given node declares
        :param int num_cores: number of cores that current node declares
        :param client_id: id of a node that wants to get a next subtask
        :return ComputeTaskDef | None: return ComputeTaskDef if a client with given id receives a subtask to compute
        and None otherwise
        """
        return  # Implement in derived class

    @abc.abstractmethod
    def short_extra_data_repr(self, perf_index=None):
        """ Should return a short string with general task description that may be used for logging or stats gathering.
        :param int perf_index: performance index that may affect task description
        :return str:
        """
        return  # Implement in derived class

    @abc.abstractmethod
    def needs_computation(self):
        """ Return information if there are still some subtasks that may be dispended
        :return bool: True if there are still subtask that should be computed, False otherwise
        """
        return  # Implement in derived class

    @abc.abstractmethod
    def finished_computation(self):
        """ Return information if tasks has been fully computed
        :return bool: True if there is all tasks has been computed and verified
        """
        return False

    @abc.abstractmethod
    def computation_finished(self, subtask_id, task_result, dir_manager=None, result_type=0):
        """ Inform about finished subtask
        :param subtask_id: finished subtask id
        :param task_result: task result, can be binary data or list of files
        :param DirManager dir_manager: directory manager that keeps information where results are kept
        :param result_type: result_types representation
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
    def get_total_tasks(self):
        """ Return total number of tasks that should be computed
        :return int: number should be greater than 0
        """
        return  # Implement in derived class

    @abc.abstractmethod
    def get_active_tasks(self):
        """ Return number of tasks that are currently being computed
        :return int: number should be between 0 and a result of get_total_tasks
        """
        return  # Implement in derived class

    @abc.abstractmethod
    def get_tasks_left(self):
        """ Return number of tasks that still should be computed
        :return int: number should be between 0 and a result of get_total_tasks
        """
        return  # Implement in derived class

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
    def get_progress(self):
        """ Return task computations progress
        :return float: Return number between 0.0 and 1.0.
        """
        return  # Implement in derived class

    @abc.abstractmethod
    def accept_results_delay(self):
        """ asks there should be a added subtask_id and delay_time as an argument. The name should be also changed
        from "accept" to "set down" or something similar. The result of this method is a delay value, not a boolean
        as a name is suggesting.
        :return:
        """
        return 0.0

    @abc.abstractmethod
    def get_resources(self, task_id, resource_header, resource_type=0):
        """ Compare resources that were declared by client in a resource_header and prepare lacking one. Method of
        preparing resources depends from declared resource_type
        :param task_id: FIXME
        :param ResourceHeader resource_header: description of resources that computing node already have for this task
        :param int resource_type: resource type from resources_types (0 for zip, 1 for hash list)
        :return None | str | (TaskResourceHeader, list): result depends on return on resource_type
        """
        return None

    @abc.abstractmethod
    def update_task_state(self, task_state):
        """Update some task information taking into account new state.
        :param TaskState task_state:
        """
        return  # Implement in derived class

    @abc.abstractmethod
    def get_price_mod(self, subtask_id):
        """ Return price modifier for given subtask. This number may be taken into account during increasing
        or decreasing trust for given node after successful or failed computation.
        :param subtask_id:
        :return int:
        """
        return  # Implement in derived class

    @abc.abstractmethod
    def get_trust_mod(self, subtask_id):
        """ Return trust modifier for given subtask. This number may be taken into account during increasing
        or decreasing trust for given node after successful or failed computation.
        :param subtask_id:
        :return int:
        """
        return  # Implement in derived class

    @abc.abstractmethod
    def add_resources(self, resources):
        """ Add resources to a task
        :param resources:
        """
        return  # Implement in derived class


result_types = {'data': 0, 'files': 1}
resource_types = {'zip': 0, 'parts': 1}
