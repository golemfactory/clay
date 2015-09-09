import time
import abc


class TaskHeader:
    #######################
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
    #######################
    def __init__(self):
        pass

    #######################
    @abc.abstractmethod
    def build(self):
        return


class ComputeTaskDef(object):
    #######################
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
    #######################
    def __init__(self, header, src_code):
        self.src_code = src_code
        self.header = header

    #######################
    @abc.abstractmethod
    def initialize(self):
        return  # Implement in derived class

    #######################
    @abc.abstractmethod
    def query_extra_data(self, perf_index, num_cores=1, client_id=None):
        return  # Implement in derived class

    #######################
    @abc.abstractmethod
    def short_extra_data_repr(self, perf_index):
        return  # Implement in derived class

    #######################
    @abc.abstractmethod
    def needs_computation(self):
        return  # Implement in derived class

    #######################
    @abc.abstractmethod
    def computation_started(self, extra_data):
        return  # Implement in derived class

    #######################
    @abc.abstractmethod
    def computation_finished(self, subtask_id, task_result, dir_manager=None, result_type=0):
        return  # Implement in derived class

    #######################
    @abc.abstractmethod
    def computation_failed(self, subtask_id):
        return  # Implement in derived class

    #######################
    @abc.abstractmethod
    def verify_subtask(self, subtask_id):
        return  # Implement in derived class

    #######################
    @abc.abstractmethod
    def verify_task(self):
        return  # Implement in derived class

    #######################
    @abc.abstractmethod
    def get_total_tasks(self):
        return  # Implement in derived class

    #######################
    @abc.abstractmethod
    def get_total_chunks(self):
        return  # Implement in derived class

    #######################
    @abc.abstractmethod
    def get_active_tasks(self):
        return  # Implement in derived class

    #######################
    @abc.abstractmethod
    def get_active_chunks(self):
        return  # Implement in derived class

    #######################
    @abc.abstractmethod
    def get_chunks_left(self):
        return  # Implement in derived class

    #######################
    @abc.abstractmethod
    def get_progress(self):
        return  # Implement in derived class

    #######################
    @abc.abstractmethod
    def accept_results_delay(self):
        return 0.0

    #######################
    @abc.abstractmethod
    def prepare_resource_delta(self, task_id, resource_header):
        return None

    #######################
    @abc.abstractmethod
    def test_task(self):
        return False

    #######################
    @abc.abstractmethod
    def update_task_state(self, task_state):
        return  # Implement in derived class

    #######################
    @abc.abstractmethod
    def get_price_mod(self, subtask_id):
        return  # Implement in derived class

    #######################
    @abc.abstractmethod
    def get_trust_mod(self, subtask_id):
        return  # Implement in derived class

    #######################
    @classmethod
    def build_task(cls, task_builder):
        assert isinstance(task_builder, TaskBuilder)
        return task_builder.build()


result_types = {'data': 0, 'files': 1}
