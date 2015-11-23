import time
import abc


class TaskHeader:
    def __init__(self, client_id, task_id, task_owner_address, task_owner_port, task_owner_key_id, environment,
                 task_owner=None, ttl=0.0, subtask_timeout=0.0, resource_size=0, estimated_memory=0, min_version=1.0):
        self.task_id = task_id
        self.task_owner_key_id = task_owner_key_id
        self.task_owner_address = task_owner_address
        self.task_owner_port = task_owner_port
        self.task_owner = task_owner
        self.last_checking = time.time()
        self.ttl = ttl
        self.subtask_timeout = subtask_timeout
        self.client_id = client_id
        self.resource_size = resource_size
        self.environment = environment
        self.estimated_memory = estimated_memory
        self.min_version = min_version


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
        """
        Verify given subtask
        :param subtask_id:
        :return bool: True if a subtask passed verification
        """
        return  # Implement in derived class

    @abc.abstractmethod
    def verify_task(self):
        return  # Implement in derived class

    @abc.abstractmethod
    def get_total_tasks(self):
        return  # Implement in derived class

    @abc.abstractmethod
    def get_total_chunks(self):
        return  # Implement in derived class

    @abc.abstractmethod
    def get_active_tasks(self):
        return  # Implement in derived class

    @abc.abstractmethod
    def get_active_chunks(self):
        return  # Implement in derived class

    @abc.abstractmethod
    def get_chunks_left(self):
        return  # Implement in derived class

    @abc.abstractmethod
    def get_progress(self):
        return  # Implement in derived class

    @abc.abstractmethod
    def accept_results_delay(self):
        return 0.0

    @abc.abstractmethod
    def prepare_resource_delta(self, task_id, resource_header):
        return None

    @abc.abstractmethod
    def test_task(self):
        return False

    @abc.abstractmethod
    def update_task_state(self, task_state):
        return  # Implement in derived class

    @abc.abstractmethod
    def get_price_mod(self, subtask_id):
        return  # Implement in derived class

    @abc.abstractmethod
    def get_trust_mod(self, subtask_id):
        return  # Implement in derived class

    @classmethod
    def build_task(cls, task_builder):
        assert isinstance(task_builder, TaskBuilder)
        return task_builder.build()


result_types = {'data': 0, 'files': 1}
