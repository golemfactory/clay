import os
import glob
import uuid
import logging
import cPickle as pickle

from golem.task.TaskState import TaskStatus
from golem.task.TaskBase import Task

from examples.gnr.task.InfoTask import InfoTaskBuilder, InfoTaskDefinition
from examples.gnr.task.UpdateOtherGolemsTask import UpdateOtherGolemsTaskBuilder, UpdateOtherGolemsTaskDefinition

from GNRApplicationLogic import GNRApplicationLogic

logger = logging.getLogger(__name__)

class GNRAdmApplicationLogic(GNRApplicationLogic):
    ######################
    def __init__(self):
        GNRApplicationLogic.__init__(self)
        self.start_nodes_manager_function = lambda: None

        self.add_tasks_client = None

    ######################
    def register_start_nodes_manager_function(self, func):
        self.start_nodes_manager_function = func

    ######################
    def start_nodes_manager_server(self):
        self.start_nodes_manager_function()

    ######################
    def send_test_tasks(self):
        path = os.path.join(os.environ.get('GOLEM'), 'save/test')
        self.add_and_start_tasks_from_files(glob.glob(os.path.join(path, '*.gt')))

    ######################
    def update_other_golems(self, golem_dir):
        task_definition         = UpdateOtherGolemsTaskDefinition()
        task_definition.task_id  = "{}".format(uuid.uuid4())
        task_definition.src_file          = os.path.normpath(os.path.join(os.environ.get('GOLEM'), "examples/tasks/update_golem.py"))
        task_definition.total_subtasks    = 100
        task_definition.full_task_timeout  = 4 * 60 * 60
        task_definition.subtask_timeout   = 20 * 60

        task_builder = UpdateOtherGolemsTaskBuilder(self.client.get_id(),
                                          task_definition,
                                        self.client.get_root_path(), golem_dir)

        task = Task.build_task( task_builder)
        self.add_task_from_definition(task_definition)
        self.client.enqueue_new_task(task)

        logger.info("Update with {}".format(golem_dir))


    ######################
    def send_info_task(self, iterations, full_task_timeout, subtask_timeout):
        info_task_definition = InfoTaskDefinition()
        info_task_definition.task_id           = "{}".format(uuid.uuid4())
        info_task_definition.src_file          = os.path.normpath(os.path.join(os.environ.get('GOLEM'), "examples/tasks/send_snapshot.py"))
        info_task_definition.total_subtasks    = iterations
        info_task_definition.full_task_timeout  = full_task_timeout
        info_task_definition.subtask_timeout   = subtask_timeout
        info_task_definition.manager_address   = self.client.config_desc.manager_address
        info_task_definition.manager_port      = self.client.config_desc.manager_port

        task_builder = InfoTaskBuilder(self.client.get_id(),
                                          info_task_definition,
                                        self.client.get_root_path())

        task = Task.build_task( task_builder)
        self.add_task_from_definition(info_task_definition)
        self.client.enqueue_new_task(task)


    ######################
    def start_add_task_client(self):
        import zerorpc
        self.add_tasks_client = zerorpc.Client()
        self.add_tasks_client.connect("tcp://127.0.0.1:{}".format(self.client.get_plugin_port()))

    ######################
    def check_network_state(self):
        GNRApplicationLogic.check_network_state(self)
        if self.add_tasks_client:
            self.add_and_start_tasks_from_files(self.add_tasks_client.get_tasks())

    ######################
    def add_and_start_tasks_from_files(self, files):
        tasks = []
        for task_file in files:
            try:
                task_state = self.__read_task_from_file(task_file)
                tasks.append(task_state)
            except Exception as ex:
                logger.error("Wrong task file {}, {}".format(task_file, str(ex)))

        self.add_tasks (tasks)
        for task in tasks:
            self.start_task(task.definition.task_id)

    ######################
    def __read_task_from_file(self, task_file):
        task_state = self._get_new_task_state()
        task_state.status = TaskStatus.notStarted
        with open(task_file, 'r') as f:
            task_state.definition = pickle.loads(f.read())
        task_state.definition.task_id = "{}".format(uuid.uuid4())
        return task_state
