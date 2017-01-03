import abc
import logging
import time
from copy import deepcopy

from golem.core.simpleserializer import CBORSerializer, DictSerializer
from golem.core.variables import APP_VERSION
from golem.docker.image import DockerImage
from golem.network.p2p.node import Node

logger = logging.getLogger("golem.task")


class TaskHeader(object):
    """ Task header describe general information about task as an request and is propagated in the
        network as an offer for computing nodes
    """
    def __init__(self, node_name, task_id, task_owner_address, task_owner_port, task_owner_key_id, environment,
                 task_owner=None, deadline=0.0, subtask_timeout=0.0, resource_size=0, estimated_memory=0,
                 min_version=APP_VERSION, max_price=0.0, docker_images=None, signature=None):

        self.task_id = task_id
        # TODO Remove task_owner_key_id, task_onwer_address and task_owner_port
        self.task_owner_key_id = task_owner_key_id
        self.task_owner_address = task_owner_address
        self.task_owner_port = task_owner_port
        self.task_owner = task_owner
        # TODO change last_checking param
        self.last_checking = time.time()
        self.deadline = deadline
        self.subtask_timeout = subtask_timeout
        self.node_name = node_name
        self.resource_size = resource_size
        self.environment = environment
        self.estimated_memory = estimated_memory
        self.min_version = min_version
        self.docker_images = docker_images
        self.max_price = max_price
        self.signature = signature

    def to_binary(self):
        return self.dict_to_binary(self.to_dict())

    def to_dict(self):
        return DictSerializer.dump(self, typed=False)

    @staticmethod
    def from_dict(dictionary):
        th = DictSerializer.load(dictionary, as_class=TaskHeader)
        th.last_checking = time.time()

        if isinstance(th.task_owner, dict):
            th.task_owner = DictSerializer.load(th.task_owner, as_class=Node)
        if hasattr(th, 'docker_images') and th.docker_images is not None:
            for i, di in enumerate(th.docker_images):
                if isinstance(di, dict):
                    th.docker_images[i] = DictSerializer.load(di, as_class=DockerImage)
        return th

    @classmethod
    def dict_to_binary(cls, dictionary):
        self_dict = dict(dictionary)
        self_dict.pop('last_checking', None)
        self_dict.pop('signature', None)

        self_dict['task_owner'] = cls._ordered(self_dict['task_owner'])
        if self_dict.get('docker_images'):
            self_dict['docker_images'] = [cls._ordered(di) for di in self_dict['docker_images']]

        return CBORSerializer.dumps(cls._ordered(self_dict))

    @staticmethod
    def _ordered(dictionary):
        return sorted(dictionary.items())


class TaskBuilder(object):
    def __init__(self):
        pass

    @abc.abstractmethod
    def build(self):
        return


class ComputeTaskDef(object):
    def __init__(self):
        self.task_id = ""
        self.subtask_id = ""
        self.deadline = ""
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
        self.docker_images = None


class TaskEventListener(object):
    def __init__(self):
        pass

    def notify_update_task(self, task_id):
        pass


class Task(object):

    class ExtraData(object):
        def __init__(self, should_wait=False, ctd=None, **kwargs):
            self.should_wait = should_wait
            self.ctd = ctd

            for key, value in kwargs.iteritems():
                setattr(self, key, value)

    @classmethod
    def build_task(cls, task_builder):
        assert isinstance(task_builder, TaskBuilder)
        return task_builder.build()

    def __init__(self, header, src_code):
        self.src_code = src_code
        self.header = header
        self.undeletable = []

        self.listeners = []

    def __getstate__(self):
        state_attr = vars(self).keys()
        state_attr.remove('listeners')
        return {attr: deepcopy(getattr(self, attr)) for attr in state_attr}

    def __setstate__(self, dict_):
        self.__dict__ = dict_
        self.listeners = []

    def register_listener(self, listener):
        assert isinstance(listener, TaskEventListener)
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
    def query_extra_data(self, perf_index, num_cores=1, node_id=None, node_name=None):
        """ Called when a node asks with given parameters asks for a new subtask to compute.
        :param int perf_index: performance that given node declares
        :param int num_cores: number of cores that current node declares
        :param None|str node_id: id of a node that wants to get a next subtask
        :param None|str node_name: name of a node that wants to get a next subtask
        :return ExtraData
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
    def computation_finished(self, subtask_id, task_result, result_type=0):
        """ Inform about finished subtask
        :param subtask_id: finished subtask id
        :param task_result: task result, can be binary data or list of files
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
    def get_resources(self, task_id, resource_header, resource_type=0, tmp_dir=None):
        """ Compare resources that were declared by client in a resource_header and prepare lacking one. Method of
        preparing resources depends from declared resource_type
        :param task_id: FIXME
        :param ResourceHeader resource_header: description of resources that computing node already have for this task
        :param int resource_type: resource type from resources_types (0 for zip, 1 for hash list)
        :param str tmp_dir: additional directory that can be used during file transfer
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

    def get_stdout(self, subtask_id):
        """ Return stdout received after computation of subtask_id, if there is no data available
        return empty string
        :param subtask_id:
        :return str:
        """
        return ""

    def get_stderr(self, subtask_id):
        """ Return stderr received after computation of subtask_id, if there is no data available
        return emtpy string
        :param subtask_id:
        :return str:
        """
        return ""

    def get_results(self, subtask_id):
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

    def get_output_names(self):
        """ Return list of files containing final import task results
        :return list:
        """
        return []


result_types = {'data': 0, 'files': 1}
resource_types = {'zip': 0, 'parts': 1, 'hashes': 2}
