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

class GNRClientEventListener( GolemClientEventListener ):
    #####################
    def __init__( self, logic ):
        self.logic = logic
        GolemClientEventListener.__init__( self )

    #####################
    def taskUpdated( self, taskId ):
        self.logic.taskStatusChanged( taskId )

    #####################
    def checkNetworkState( self ):
        self.logic.checkNetworkState()

taskToRemoveStatus = [ TaskStatus.aborted, TaskStatus.failure, TaskStatus.finished, TaskStatus.paused ]

class GNRApplicationLogic( QtCore.QObject ):
    ######################
    def __init__( self ):
        QtCore.QObject.__init__( self )
        self.tasks              = {}
        self.testTasks          = {}
        self.taskTypes          = {}
        self.customizer         = None
        self.rootPath           = os.path.join( os.environ.get('GOLEM'), 'examples/gnr' )
        self.nodesManagerClient = None
        self.addNewNodesFunction = lambda x: None

    ######################
    def registerGui( self, gui, customizerClass ):
        self.customizer = customizerClass( gui, self )

    ######################
    def registerClient( self, client ):
        self.client = client
        self.client.registerListener( GNRClientEventListener( self ) )

    ######################
    def registerStartNewNodeFunction( self, func ):
        self.addNewNodesFunction = func

    ######################
    def checkNetworkState( self ):
        listenPort = self.client.p2pservice.p2pServer.curPort
        taskServerPort = self.client.taskServer.curPort
        if listenPort == 0 or taskServerPort == 0:
            self.customizer.gui.ui.errorLabel.setText("Application not listening, check config file.")
            return
        peersNum = len( self.client.p2pservice.peers )
        if peersNum == 0:
            self.customizer.gui.ui.errorLabel.setText("Not connected to Golem Network. Check seed parameters.")
            return

        self.customizer.gui.ui.errorLabel.setText("")

    ######################
    def startNodesManagerClient( self):
        if self.client:
            configDesc = self.client.configDesc
            self.nodesManagerClient = NodesManagerUidClient ( configDesc.clientUid,
                                                           configDesc.managerAddress,
                                                           configDesc.managerPort,
                                                           None,
                                                           self)
            self.nodesManagerClient.start()
            self.client.registerNodesManagerClient( self.nodesManagerClient )
        else:
            logger.error("Can't register nodes manager client. No client instance.")

    ######################
    def getTask( self, taskId ):
        assert taskId in self.tasks, "GNRApplicationLogic: task {} not added".format( taskId )

        return self.tasks[ taskId ]

    ######################
    def getTaskTypes( self ):
        return self.taskTypes

    ######################
    def getStatus( self ):
        return self.client.getStatus()

    ######################
    def getAboutInfo( self ):
        return self.client.getAboutInfo()

    ######################
    def getConfig( self ):
        return self.client.configDesc

    ######################
    def getTaskType( self, name ):
        if name in self.taskTypes:
            return self.taskTypes[ name ]
        else:
            assert False, "Task {} not registered".format( name )

    ######################
    def changeConfig (  self, cfgDesc ):
        oldCfgDesc = self.client.configDesc
        if ( oldCfgDesc.managerAddress != cfgDesc.managerAddress ) or ( oldCfgDesc.managerPort != cfgDesc.managerPort ):
            self.nodesManagerClient.dropConnection()
            del self.nodesManagerClient
            self.nodesManagerClient = NodesManagerClient( cfgDesc.clientUid,
                                                          cfgDesc.managerAddress,
                                                          cfgDesc.managerPort,
                                                          None,
                                                          self )

            self.nodesManagerClient.start()
            self.client.registerNodesManagerClient( self.nodesManagerClient )
        self.client.changeConfig( cfgDesc )

    ######################
    def _getNewTaskState( self ):
        return GNRTaskState()

    ######################
    def startTask( self, taskId ):
        ts = self.getTask( taskId )

        if ts.taskState.status != TaskStatus.notStarted:
            errorMsg = "Task already started"
            self.__showErrorWindow( errorMsg )
            logger.error( errorMsg )
            return

        tb = self._getBuilder( ts )

        t = Task.buildTask( tb )

        self.client.enqueueNewTask( t )

    ######################
    def _getBuilder( self, taskState ):
        #FIXME Bardzo tymczasowe rozwiazanie dla zapewnienia zgodnosci
        if hasattr(taskState.definition, "renderer"):
            taskState.definition.taskType = taskState.definition.renderer

        return self.taskTypes[ taskState.definition.taskType ].taskBuilderType( self.client.getId(), taskState.definition, self.client.getRootPath( ) )

    ######################
    def restartTask( self, taskId ):
        self.client.restartTask( taskId )

    ######################
    def abortTask( self, taskId ):
        self.client.abortTask( taskId )

    ######################
    def pauseTask( self, taskId ):
        self.client.pauseTask( taskId )

    ######################
    def resumeTask( self, taskId ):
        self.client.resumeTask( taskId )

    ######################
    def deleteTask( self, taskId ):
        self.client.deleteTask( taskId )
        self.customizer.removeTask( taskId )

    ######################
    def showTaskDetails( self, taskId ):
        self.customizer.showDetailsDialog(taskId)

    ######################
    def showNewTaskDialog ( self, taskId ):
        self.customizer.showNewTaskDialog(taskId)

    ######################
    def restartSubtask ( self, subtaskId ):
        self.client.restartSubtask( subtaskId )

    ######################
    def changeTask (self, taskId ):
        self.customizer.showChangeTaskDialog( taskId )

    ######################
    def showTaskResult( self, taskId ):
        self.customizer.showTaskResult( taskId )

    ######################
    def changeTimeouts ( self, taskId, fullTaskTimeout, subtaskTimeout, minSubtaskTime ):
        if taskId in self.tasks:
            task = self.tasks[taskId]
            task.definition.fullTaskTimeout = fullTaskTimeout
            task.definition.minSubtaskTime = minSubtaskTime
            task.definition.subtaskTimeout = subtaskTimeout
            self.client.changeTimeouts(taskId, fullTaskTimeout, subtaskTimeout, minSubtaskTime )
            self.customizer.updateTaskAdditionalInfo( task )
        else:
            logger.error("It's not my task: {} ", taskId )

    ######################
    def getTestTasks( self ):
        return self.testTasks

    ######################
    def addTaskFromDefinition ( self, definition ):
        taskState = self._getNewTaskState()
        taskState.status = TaskStatus.notStarted

        taskState.definition = definition

        self.addTasks( [taskState] )

    ######################
    def addTasks( self, tasks ):

        if len( tasks ) == 0:
            return

        for t in tasks:
            if t.definition.taskId not in self.tasks:
                self.tasks[ t.definition.taskId ] = t
                self.customizer.addTask( t )
            else:
                self.tasks[ t.definition.taskId ] = t

        self.customizer.updateTasks( self.tasks )

    ######################
    def registerNewTaskType(self, taskType):
        if taskType.name not in self.taskTypes:
            self.taskTypes[ taskType.name ] = taskType
        else:
            assert False, "Task type {} already registered".format( taskType.name )

    ######################
    def registerNewTestTaskType( self, testTaskInfo ):
        if testTaskInfo.name not in self.testTasks:
            self.testTasks[ testTaskInfo.name ] = testTaskInfo
        else:
            assert False, "Test task {} already registered".format( testTaskInfo.name )

    ######################
    def saveTask( self, taskState, filePath ):
        with open( filePath, "wb" ) as f:
            tspickled = pickle.dumps( taskState )
            f.write( tspickled )

    ######################
    def recountPerformance( self, numCores ):
        testFile = os.path.join( os.environ.get('GOLEM'), 'testtasks\minilight\cornellbox.ml.txt' )
        resultFile = os.path.join( os.environ.get( 'GOLEM' ), 'examples\\gnr\\node_data\\minilight.ini')
        estimatedPerf =  makePerfTest(testFile, resultFile, numCores)
        return estimatedPerf


    ######################
    def runTestTask( self, taskState ):
        if self._validateTaskState( taskState ):

            tb = self._getBuilder( taskState )

            t = Task.buildTask( tb )

            self.tt = TaskTester( t, self.client.getRootPath(), self._testTaskComputationFinished )

            self.progressDialog = TestingTaskProgressDialog( self.customizer.gui.window  )
            self.progressDialog.show()

            self.tt.run()

            return True
        else:
            return False

    ######################
    def getEnvironments( self ) :
        return self.client.getEnvironments()

    ######################
    def changeAcceptTasksForEnvironment( self, envId, state ):
        self.client.changeAcceptTasksForEnvironment( envId, state )

    ######################
    def _testTaskComputationFinished( self, success, estMem = 0 ):
        if success:
            self.progressDialog.showMessage("Test task computation success!")
        else:
            self.progressDialog.showMessage("Task test computation failure... Check resources.")
        if self.customizer.newTaskDialogCustomizer:
            self.customizer.newTaskDialogCustomizer.testTaskComputationFinished( success, estMem )

    ######################
    def taskStatusChanged( self, taskId ):

        if taskId in self.tasks:
            ts = self.client.querryTaskState( taskId )
            assert isinstance( ts, TaskState )
            self.tasks[taskId].taskState = ts
            self.customizer.updateTasks( self.tasks )
            if ts.status in taskToRemoveStatus:
                self.client.taskServer.removeTaskHeader( taskId )
                self.client.p2pservice.removeTask( taskId )
        else:
            assert False, "Should never be here!"


        if self.customizer.currentTaskHighlighted.definition.taskId == taskId:
            self.customizer.updateTaskAdditionalInfo( self.tasks[ taskId ] )

    ######################
    def _showErrorWindow( self, text ):
        from PyQt4.QtGui import QMessageBox
        msBox = QMessageBox( QMessageBox.Critical, "Error", text )
        msBox.exec_()
        msBox.show()


    ######################
    def _validateTaskState( self, taskState ):

        td = taskState.definition
        if not os.path.exists( td.mainProgramFile ):
            self._showErrorWindow( "Main program file does not exist: {}".format( td.mainProgramFile ) )
            return False
        return True

