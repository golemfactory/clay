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
        self.startNodesManagerFunction = lambda: None

        self.addTasksClient = None

    ######################
    def registerStartNodesManagerFunction(self, func):
        self.startNodesManagerFunction = func

    ######################
    def startNodesManagerServer(self):
        self.startNodesManagerFunction()

    ######################
    def sendTestTasks(self):
        path = os.path.join(os.environ.get('GOLEM'), 'save/test')
        self.addAndStartTasksFromFiles(glob.glob(os.path.join(path, '*.gt')))

    ######################
    def updateOtherGolems(self, golemDir):
        taskDefinition         = UpdateOtherGolemsTaskDefinition()
        taskDefinition.task_id  = "{}".format(uuid.uuid4())
        taskDefinition.src_file          = os.path.normpath(os.path.join(os.environ.get('GOLEM'), "examples/tasks/updateGolem.py"))
        taskDefinition.totalSubtasks    = 100
        taskDefinition.full_task_timeout  = 4 * 60 * 60
        taskDefinition.subtask_timeout   = 20 * 60

        task_builder = UpdateOtherGolemsTaskBuilder(self.client.get_id(),
                                          taskDefinition,
                                        self.client.get_root_path(), golemDir)

        task = Task.build_task( task_builder)
        self.addTaskFromDefinition(taskDefinition)
        self.client.enqueue_new_task(task)

        logger.info("Update with {}".format(golemDir))


    ######################
    def sendInfoTask(self, iterations, full_task_timeout, subtask_timeout):
        infoTaskDefinition = InfoTaskDefinition()
        infoTaskDefinition.task_id           = "{}".format(uuid.uuid4())
        infoTaskDefinition.src_file          = os.path.normpath(os.path.join(os.environ.get('GOLEM'), "examples/tasks/send_snapshot.py"))
        infoTaskDefinition.totalSubtasks    = iterations
        infoTaskDefinition.full_task_timeout  = full_task_timeout
        infoTaskDefinition.subtask_timeout   = subtask_timeout
        infoTaskDefinition.manager_address   = self.client.config_desc.manager_address
        infoTaskDefinition.manager_port      = self.client.config_desc.manager_port

        task_builder = InfoTaskBuilder(self.client.get_id(),
                                          infoTaskDefinition,
                                        self.client.get_root_path())

        task = Task.build_task( task_builder)
        self.addTaskFromDefinition(infoTaskDefinition)
        self.client.enqueue_new_task(task)


    ######################
    def startAddTaskClient(self):
        import zerorpc
        self.addTasksClient = zerorpc.Client()
        self.addTasksClient.connect("tcp://127.0.0.1:{}".format(self.client.get_plugin_port()))

    ######################
    def check_network_state(self):
        GNRApplicationLogic.check_network_state(self)
        if self.addTasksClient:
            self.addAndStartTasksFromFiles(self.addTasksClient.get_tasks())

    ######################
    def addAndStartTasksFromFiles(self, files):
        tasks = []
        for taskFile in files:
            try:
                task_state = self.__readTaskFromFile(taskFile)
                tasks.append(task_state)
            except Exception as ex:
                logger.error("Wrong task file {}, {}".format(taskFile, str(ex)))

        self.add_tasks (tasks)
        for task in tasks:
            self.start_task(task.definition.task_id)

    ######################
    def __readTaskFromFile(self, taskFile):
        task_state = self._getNewTaskState()
        task_state.status = TaskStatus.notStarted
        with open(taskFile, 'r') as f:
            task_state.definition = pickle.loads(f.read())
        task_state.definition.task_id = "{}".format(uuid.uuid4())
        return task_state