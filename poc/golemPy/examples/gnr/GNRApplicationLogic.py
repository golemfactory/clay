import os
import logging
import uuid
import cPickle as pickle
from PyQt4 import QtCore


from examples.gnr.ui.TestingTaskProgressDialog import TestingTaskProgressDialog
from golem.task.TaskState import TaskStatus
from examples.gnr.GNRTaskState import GNRTaskState
from examples.gnr.task.TaskTester import TaskTester
from golem.task.TaskBase import Task
from golem.task.TaskState import TaskState
from golem.Client import GolemClientEventListener
from golem.manager.client.NodesManagerClient import NodesManagerUidClient, NodesManagerClient

from testtasks.minilight.src.minilight import makePerfTest

logger = logging.getLogger(__name__)

class GNRClientEventListener(GolemClientEventListener):
    #####################
    def __init__(self, logic):
        self.logic = logic
        GolemClientEventListener.__init__(self)

    #####################
    def task_updated(self, task_id):
        self.logic.task_statusChanged(task_id)

    #####################
    def check_network_state(self):
        self.logic.check_network_state()

taskToRemoveStatus = [ TaskStatus.aborted, TaskStatus.failure, TaskStatus.finished, TaskStatus.paused ]

class GNRApplicationLogic(QtCore.QObject):
    ######################
    def __init__(self):
        QtCore.QObject.__init__(self)
        self.tasks              = {}
        self.test_tasks          = {}
        self.task_types          = {}
        self.customizer         = None
        self.root_path           = os.path.join(os.environ.get('GOLEM'), 'examples/gnr')
        self.nodes_manager_client = None
        self.add_new_nodes_function = lambda x: None

    ######################
    def register_gui(self, gui, customizerClass):
        self.customizer = customizerClass(gui, self)

    ######################
    def register_client(self, client):
        self.client = client
        self.client.register_listener(GNRClientEventListener(self))

    ######################
    def registerStartNewNodeFunction(self, func):
        self.add_new_nodes_function = func

    ######################
    def get_res_dirs(self):
        return self.client.get_res_dirs()

    ######################
    def remove_computed_files(self):
        self.client.remove_computed_files()

    ######################
    def remove_distributed_files(self):
        self.client.remove_distributed_files()

    ######################
    def remove_received_files(self):
        self.client.remove_received_files()

    ######################
    def check_network_state(self):
        listen_port = self.client.p2pservice.cur_port
        task_server_port = self.client.task_server.cur_port
        if listen_port == 0 or task_server_port == 0:
            self.customizer.gui.ui.errorLabel.setText("Application not listening, check config file.")
            return
        peers_num = len(self.client.p2pservice.peers)
        if peers_num == 0:
            self.customizer.gui.ui.errorLabel.setText("Not connected to Golem Network. Check seed parameters.")
            return

        self.customizer.gui.ui.errorLabel.setText("")

    ######################
    def startNodesManagerClient(self):
        if self.client:
            config_desc = self.client.config_desc
            self.nodes_manager_client = NodesManagerUidClient (config_desc.client_uid,
                                                           config_desc.manager_address,
                                                           config_desc.manager_port,
                                                           None,
                                                           self)
            self.nodes_manager_client.start()
            self.client.register_nodes_manager_client(self.nodes_manager_client)
        else:
            logger.error("Can't register nodes manager client. No client instance.")

    ######################
    def get_task(self, task_id):
        assert task_id in self.tasks, "GNRApplicationLogic: task {} not added".format(task_id)

        return self.tasks[ task_id ]

    ######################
    def get_task_types(self):
        return self.task_types

    ######################
    def get_status(self):
        return self.client.get_status()

    ######################
    def get_about_info(self):
        return self.client.get_about_info()

    ######################
    def getConfig(self):
        return self.client.config_desc

    ######################
    def quit(self):
        self.client.quit()

    ######################
    def get_task_type(self, name):
        task_type = self.tasksType[ name ]
        if task_type:
            return task_type
        else:
            assert False, "Task {} not registered".format(name)

    ######################
    def change_config ( self, cfg_desc):
        oldCfgDesc = self.client.config_desc
        if (oldCfgDesc.manager_address != cfg_desc.manager_address) or (oldCfgDesc.manager_port != cfg_desc.manager_port):
            if self.nodes_manager_client is not None:
                self.nodes_manager_client.dropConnection()
                del self.nodes_manager_client
            self.nodes_manager_client = NodesManagerUidClient(cfg_desc.client_uid,
                                                          cfg_desc.manager_address,
                                                          cfg_desc.manager_port,
                                                          None,
                                                          self)

            self.nodes_manager_client.start()
            self.client.register_nodes_manager_client(self.nodes_manager_client)
        self.client.change_config(cfg_desc)

    ######################
    def _get_new_task_state(self):
        return GNRTaskState()

    ######################
    def start_task(self, task_id):
        ts = self.get_task(task_id)

        if ts.task_state.status != TaskStatus.notStarted:
            error_msg = "Task already started"
            self._showErrorWindow(error_msg)
            logger.error(error_msg)
            return

        tb = self._get_builder(ts)

        t = Task.build_task(tb)

        self.client.enqueue_new_task(t)

    ######################
    def _get_builder(self, task_state):
        #FIXME Bardzo tymczasowe rozwiazanie dla zapewnienia zgodnosci
        if hasattr(task_state.definition, "renderer"):
            task_state.definition.task_type = task_state.definition.renderer

        return self.task_types[ task_state.definition.task_type ].task_builder_type(self.client.get_id(), task_state.definition, self.client.get_root_path())

    ######################
    def restart_task(self, task_id):
        self.client.restart_task(task_id)

    ######################
    def abort_task(self, task_id):
        self.client.abort_task(task_id)

    ######################
    def pause_task(self, task_id):
        self.client.pause_task(task_id)

    ######################
    def resume_task(self, task_id):
        self.client.resume_task(task_id)

    ######################
    def delete_task(self, task_id):
        self.client.delete_task(task_id)
        self.customizer.remove_task(task_id)

    ######################
    def showTaskDetails(self, task_id):
        self.customizer.showDetailsDialog(task_id)

    ######################
    def showNewTaskDialog (self, task_id):
        self.customizer.showNewTaskDialog(task_id)

    ######################
    def restart_subtask (self, subtask_id):
        self.client.restart_subtask(subtask_id)

    ######################
    def changeTask (self, task_id):
        self.customizer.showChangeTaskDialog(task_id)

    ######################
    def showTaskResult(self, task_id):
        self.customizer.showTaskResult(task_id)

    ######################
    def change_timeouts (self, task_id, full_task_timeout, subtask_timeout, min_subtask_time):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.definition.full_task_timeout = full_task_timeout
            task.definition.min_subtask_time = min_subtask_time
            task.definition.subtask_timeout = subtask_timeout
            self.client.change_timeouts(task_id, full_task_timeout, subtask_timeout, min_subtask_time)
            self.customizer.updateTaskAdditionalInfo(task)
        else:
            logger.error("It's not my task: {} ", task_id)

    ######################
    def getTestTasks(self):
        return self.test_tasks

    ######################
    def add_taskFromDefinition (self, definition):
        task_state = self._get_new_task_state()
        task_state.status = TaskStatus.notStarted

        task_state.definition = definition

        self.add_tasks([task_state])

    ######################
    def add_tasks(self, tasks):

        if len(tasks) == 0:
            return

        for t in tasks:
            if t.definition.task_id not in self.tasks:
                self.tasks[ t.definition.task_id ] = t
                self.customizer.add_task(t)
            else:
                self.tasks[ t.definition.task_id ] = t

        self.customizer.updateTasks(self.tasks)

    ######################
    def registerNewTaskType(self, task_type):
        if task_type.name not in self.task_types:
            self.task_types[ task_type.name ] = task_type
        else:
            assert False, "Task type {} already registered".format(task_type.name)

    ######################
    def registerNewTestTaskType(self, test_taskInfo):
        if test_taskInfo.name not in self.test_tasks:
            self.test_tasks[ test_taskInfo.name ] = test_taskInfo
        else:
            assert False, "Test task {} already registered".format(test_taskInfo.name)

    ######################
    def saveTask(self, task_state, file_path):
        with open(file_path, "wb") as f:
            tspickled = pickle.dumps(task_state)
            f.write(tspickled)

    ######################
    def recountPerformance(self, num_cores):
        testFile = os.path.normpath(os.path.join(os.environ.get('GOLEM'), 'testtasks/minilight/cornellbox.ml.txt'))
        resultFile = os.path.normpath(os.path.join(os.environ.get('GOLEM'), 'examples/gnr/node_data/minilight.ini'))
        estimatedPerf =  makePerfTest(testFile, resultFile, num_cores)
        return estimatedPerf


    ######################
    def runTestTask(self, task_state):
        if self._validate_task_state(task_state):

            tb = self._get_builder(task_state)

            t = Task.build_task(tb)

            self.tt = TaskTester(t, self.client.get_root_path(), self._test_taskComputationFinished)

            self.progressDialog = TestingTaskProgressDialog(self.customizer.gui.window )
            self.progressDialog.show()

            self.tt.run()

            return True
        else:
            return False

    ######################
    def get_environments(self) :
        return self.client.get_environments()

    ######################
    def change_accept_tasks_for_environment(self, env_id, state):
        self.client.change_accept_tasks_for_environment(env_id, state)

    ######################
    def _test_taskComputationFinished(self, success, est_mem = 0):
        if success:
            self.progressDialog.showMessage("Test task computation success!")
        else:
            self.progressDialog.showMessage("Task test computation failure... Check resources.")
        if self.customizer.newTaskDialogCustomizer:
            self.customizer.newTaskDialogCustomizer.test_taskComputationFinished(success, est_mem)

    ######################
    def task_statusChanged(self, task_id):

        if task_id in self.tasks:
            ts = self.client.querry_task_state(task_id)
            assert isinstance(ts, TaskState)
            self.tasks[task_id].task_state = ts
            self.customizer.updateTasks(self.tasks)
            if ts.status in taskToRemoveStatus:
                self.client.task_server.remove_task_header(task_id)
                self.client.p2pservice.remove_task(task_id)
        else:
            assert False, "Should never be here!"


        if self.customizer.currentTaskHighlighted.definition.task_id == task_id:
            self.customizer.updateTaskAdditionalInfo(self.tasks[ task_id ])

    ######################
    def _showErrorWindow(self, text):
        from PyQt4.QtGui import QMessageBox
        msBox = QMessageBox(QMessageBox.Critical, "Error", text)
        msBox.exec_()
        msBox.show()


    ######################
    def _validate_task_state(self, task_state):

        td = task_state.definition
        if not os.path.exists(td.main_program_file):
            self._showErrorWindow("Main program file does not exist: {}".format(td.main_program_file))
            return False
        return True

