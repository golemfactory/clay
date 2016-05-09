import os
import glob
import uuid
import logging
import cPickle as pickle

from golem.task.taskstate import TaskStatus
from golem.task.taskbase import Task

from gnr.task.infotask import InfoTaskBuilder, InfoTaskDefinition
from gnr.task.updateothergolemstask import UpdateOtherGolemsTaskBuilder, UpdateOtherGolemsTaskDefinition
from gnr.renderingdirmanager import find_task_script
from gnr.gnrapplicationlogic import GNRApplicationLogic
from gnr.customizers.common import get_save_dir

logger = logging.getLogger(__name__)


class AdmApplicationLogic(GNRApplicationLogic):
    """ Developer logic version with a few additions:
          - update other Golems task that replace Golem code with other files
          - info task - that sends statistics
          - send_test_tasks function that allows to send all tasks saved in subfolder of default save folder
            without being tested
          - connection with add_task_server - server which works on local machine and collect some tasks that should
            be added to Golem from external applications
          - possibility to start nodes manager that collects nodes stats

        FIXME: All this functionality should be replaced with some better solutions in the future
    """

    def __init__(self):
        GNRApplicationLogic.__init__(self)
        self.start_nodes_manager_function = lambda: None

        self.add_tasks_client = None

    def register_start_nodes_manager_function(self, func):
        self.start_nodes_manager_function = func

    def start_nodes_manager_server(self):
        self.start_nodes_manager_function()

    def send_test_tasks(self):
        path = os.path.join(get_save_dir(), "test")
        self.add_and_start_tasks_from_files(glob.glob(os.path.join(path, '*.gt')))

    def update_other_golems(self, golem_dir):
        task_definition = UpdateOtherGolemsTaskDefinition()
        task_definition.task_id = "{}".format(uuid.uuid4())
        task_definition.src_file = find_task_script("update_golem.py")
        task_definition.total_subtasks = 100
        task_definition.full_task_timeout = 4 * 60 * 60
        task_definition.subtask_timeout = 20 * 60

        task_builder = UpdateOtherGolemsTaskBuilder(self.client.get_node_name(),
                                                    task_definition,
                                                    self.client.datadir, golem_dir)

        task = Task.build_task(task_builder)
        self.add_task_from_definition(task_definition)
        self.client.enqueue_new_task(task)

        logger.info("Update with {}".format(golem_dir))

    def send_info_task(self, iterations, full_task_timeout, subtask_timeout):
        info_task_definition = InfoTaskDefinition()
        info_task_definition.task_id = "{}".format(uuid.uuid4())
        info_task_definition.src_file = find_task_script("send_snapshot.py")
        info_task_definition.total_subtasks = iterations
        info_task_definition.full_task_timeout = full_task_timeout
        info_task_definition.subtask_timeout = subtask_timeout
        info_task_definition.manager_address = self.client.config_desc.manager_address
        info_task_definition.manager_port = self.client.config_desc.manager_port

        task_builder = InfoTaskBuilder(self.client.get_node_name(),
                                       info_task_definition,
                                       self.client.datadir)

        task = Task.build_task(task_builder)
        self.add_task_from_definition(info_task_definition)
        self.client.enqueue_new_task(task)

    def start_add_task_client(self):
        import zerorpc
        self.add_tasks_client = zerorpc.Client()
        self.add_tasks_client.connect("tcp://127.0.0.1:{}".format(self.client.get_plugin_port()))

    def check_network_state(self):
        GNRApplicationLogic.check_network_state(self)
        if self.add_tasks_client:
            self.add_and_start_tasks_from_files(self.add_tasks_client.get_tasks())

    def add_and_start_tasks_from_files(self, files):
        tasks = []
        for task_file in files:
            try:
                task_state = self.__read_task_from_file(task_file)
                tasks.append(task_state)
            except Exception as ex:
                logger.error("Wrong task file {}, {}".format(task_file, str(ex)))

        self.add_tasks(tasks)
        for task in tasks:
            self.start_task(task.definition.task_id)

    def __read_task_from_file(self, task_file):
        task_state = self._get_new_task_state()
        task_state.status = TaskStatus.notStarted
        with open(task_file, 'r') as f:
            task_state.definition = pickle.loads(f.read())
        task_state.definition.task_id = "{}".format(uuid.uuid4())
        return task_state
