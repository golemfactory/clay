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
    def taskUpdated(self, task_id):
        self.logic.taskStatusChanged(task_id)

    #####################
    def checkNetworkState(self):
        self.logic.checkNetworkState()

taskToRemoveStatus = [ TaskStatus.aborted, TaskStatus.failure, TaskStatus.finished, TaskStatus.paused ]

class GNRApplicationLogic(QtCore.QObject):
    ######################
    def __init__(self):
        QtCore.QObject.__init__(self)
        self.tasks              = {}
        self.testTasks          = {}
        self.taskTypes          = {}
        self.customizer         = None
        self.root_path           = os.path.join(os.environ.get('GOLEM'), 'examples/gnr')
        self.nodesManagerClient = None
        self.addNewNodesFunction = lambda x: None

    ######################
    def registerGui(self, gui, customizerClass):
        self.customizer = customizerClass(gui, self)

    ######################
    def registerClient(self, client):
        self.client = client
        self.client.registerListener(GNRClientEventListener(self))

    ######################
    def registerStartNewNodeFunction(self, func):
        self.addNewNodesFunction = func

    ######################
    def getResDirs(self):
        return self.client.getResDirs()

    ######################
    def removeComputedFiles(self):
        self.client.removeComputedFiles()

    ######################
    def removeDistributedFiles(self):
        self.client.removeDistributedFiles()

    ######################
    def removeReceivedFiles(self):
        self.client.removeReceivedFiles()

    ######################
    def checkNetworkState(self):
        listenPort = self.client.p2pservice.cur_port
        task_server_port = self.client.task_server.cur_port
        if listenPort == 0 or task_server_port == 0:
            self.customizer.gui.ui.errorLabel.setText("Application not listening, check config file.")
            return
        peersNum = len(self.client.p2pservice.peers)
        if peersNum == 0:
            self.customizer.gui.ui.errorLabel.setText("Not connected to Golem Network. Check seed parameters.")
            return

        self.customizer.gui.ui.errorLabel.setText("")

    ######################
    def startNodesManagerClient(self):
        if self.client:
            config_desc = self.client.config_desc
            self.nodesManagerClient = NodesManagerUidClient (config_desc.client_uid,
                                                           config_desc.manager_address,
                                                           config_desc.manager_port,
                                                           None,
                                                           self)
            self.nodesManagerClient.start()
            self.client.registerNodesManagerClient(self.nodesManagerClient)
        else:
            logger.error("Can't register nodes manager client. No client instance.")

    ######################
    def get_task(self, task_id):
        assert task_id in self.tasks, "GNRApplicationLogic: task {} not added".format(task_id)

        return self.tasks[ task_id ]

    ######################
    def get_taskTypes(self):
        return self.taskTypes

    ######################
    def getStatus(self):
        return self.client.getStatus()

    ######################
    def getAboutInfo(self):
        return self.client.getAboutInfo()

    ######################
    def getConfig(self):
        return self.client.config_desc

    ######################
    def quit(self):
        self.client.quit()

    ######################
    def get_taskType(self, name):
        taskType = self.tasksType[ name ]
        if taskType:
            return taskType
        else:
            assert False, "Task {} not registered".format(name)

    ######################
    def change_config ( self, cfgDesc):
        oldCfgDesc = self.client.config_desc
        if (oldCfgDesc.manager_address != cfgDesc.manager_address) or (oldCfgDesc.manager_port != cfgDesc.manager_port):
            if self.nodesManagerClient is not None:
                self.nodesManagerClient.dropConnection()
                del self.nodesManagerClient
            self.nodesManagerClient = NodesManagerUidClient(cfgDesc.client_uid,
                                                          cfgDesc.manager_address,
                                                          cfgDesc.manager_port,
                                                          None,
                                                          self)

            self.nodesManagerClient.start()
            self.client.registerNodesManagerClient(self.nodesManagerClient)
        self.client.change_config(cfgDesc)

    ######################
    def _getNewTaskState(self):
        return GNRTaskState()

    ######################
    def startTask(self, task_id):
        ts = self.get_task(task_id)

        if ts.taskState.status != TaskStatus.notStarted:
            errorMsg = "Task already started"
            self._showErrorWindow(errorMsg)
            logger.error(errorMsg)
            return

        tb = self._getBuilder(ts)

        t = Task.buildTask(tb)

        self.client.enqueueNewTask(t)

    ######################
    def _getBuilder(self, taskState):
        #FIXME Bardzo tymczasowe rozwiazanie dla zapewnienia zgodnosci
        if hasattr(taskState.definition, "renderer"):
            taskState.definition.taskType = taskState.definition.renderer

        return self.taskTypes[ taskState.definition.taskType ].taskBuilderType(self.client.getId(), taskState.definition, self.client.getRootPath())

    ######################
    def restartTask(self, task_id):
        self.client.restartTask(task_id)

    ######################
    def abortTask(self, task_id):
        self.client.abortTask(task_id)

    ######################
    def pauseTask(self, task_id):
        self.client.pauseTask(task_id)

    ######################
    def resumeTask(self, task_id):
        self.client.resumeTask(task_id)

    ######################
    def deleteTask(self, task_id):
        self.client.deleteTask(task_id)
        self.customizer.remove_task(task_id)

    ######################
    def showTaskDetails(self, task_id):
        self.customizer.showDetailsDialog(task_id)

    ######################
    def showNewTaskDialog (self, task_id):
        self.customizer.showNewTaskDialog(task_id)

    ######################
    def restartSubtask (self, subtask_id):
        self.client.restartSubtask(subtask_id)

    ######################
    def changeTask (self, task_id):
        self.customizer.showChangeTaskDialog(task_id)

    ######################
    def showTaskResult(self, task_id):
        self.customizer.showTaskResult(task_id)

    ######################
    def change_timeouts (self, task_id, fullTaskTimeout, subtask_timeout, minSubtaskTime):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.definition.fullTaskTimeout = fullTaskTimeout
            task.definition.minSubtaskTime = minSubtaskTime
            task.definition.subtask_timeout = subtask_timeout
            self.client.change_timeouts(task_id, fullTaskTimeout, subtask_timeout, minSubtaskTime)
            self.customizer.updateTaskAdditionalInfo(task)
        else:
            logger.error("It's not my task: {} ", task_id)

    ######################
    def getTestTasks(self):
        return self.testTasks

    ######################
    def addTaskFromDefinition (self, definition):
        taskState = self._getNewTaskState()
        taskState.status = TaskStatus.notStarted

        taskState.definition = definition

        self.add_tasks([taskState])

    ######################
    def add_tasks(self, tasks):

        if len(tasks) == 0:
            return

        for t in tasks:
            if t.definition.task_id not in self.tasks:
                self.tasks[ t.definition.task_id ] = t
                self.customizer.addTask(t)
            else:
                self.tasks[ t.definition.task_id ] = t

        self.customizer.updateTasks(self.tasks)

    ######################
    def registerNewTaskType(self, taskType):
        if taskType.name not in self.taskTypes:
            self.taskTypes[ taskType.name ] = taskType
        else:
            assert False, "Task type {} already registered".format(taskType.name)

    ######################
    def registerNewTestTaskType(self, testTaskInfo):
        if testTaskInfo.name not in self.testTasks:
            self.testTasks[ testTaskInfo.name ] = testTaskInfo
        else:
            assert False, "Test task {} already registered".format(testTaskInfo.name)

    ######################
    def saveTask(self, taskState, filePath):
        with open(filePath, "wb") as f:
            tspickled = pickle.dumps(taskState)
            f.write(tspickled)

    ######################
    def recountPerformance(self, num_cores):
        testFile = os.path.normpath(os.path.join(os.environ.get('GOLEM'), 'testtasks/minilight/cornellbox.ml.txt'))
        resultFile = os.path.normpath(os.path.join(os.environ.get('GOLEM'), 'examples/gnr/node_data/minilight.ini'))
        estimatedPerf =  makePerfTest(testFile, resultFile, num_cores)
        return estimatedPerf


    ######################
    def runTestTask(self, taskState):
        if self._validateTaskState(taskState):

            tb = self._getBuilder(taskState)

            t = Task.buildTask(tb)

            self.tt = TaskTester(t, self.client.getRootPath(), self._testTaskComputationFinished)

            self.progressDialog = TestingTaskProgressDialog(self.customizer.gui.window )
            self.progressDialog.show()

            self.tt.run()

            return True
        else:
            return False

    ######################
    def getEnvironments(self) :
        return self.client.getEnvironments()

    ######################
    def changeAcceptTasksForEnvironment(self, envId, state):
        self.client.changeAcceptTasksForEnvironment(envId, state)

    ######################
    def _testTaskComputationFinished(self, success, estMem = 0):
        if success:
            self.progressDialog.showMessage("Test task computation success!")
        else:
            self.progressDialog.showMessage("Task test computation failure... Check resources.")
        if self.customizer.newTaskDialogCustomizer:
            self.customizer.newTaskDialogCustomizer.testTaskComputationFinished(success, estMem)

    ######################
    def taskStatusChanged(self, task_id):

        if task_id in self.tasks:
            ts = self.client.querryTaskState(task_id)
            assert isinstance(ts, TaskState)
            self.tasks[task_id].taskState = ts
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
    def _validateTaskState(self, taskState):

        td = taskState.definition
        if not os.path.exists(td.mainProgramFile):
            self._showErrorWindow("Main program file does not exist: {}".format(td.mainProgramFile))
            return False
        return True

