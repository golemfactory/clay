import os
import logging
import uuid
import glob
import cPickle as pickle
from PyQt4 import QtCore

from examples.gnr.task.InfoTask import InfoTaskBuilder, InfoTaskDefinition
from examples.gnr.task.UpdateOtherGolemsTask import UpdateOtherGolemsTaskBuilder, UpdateOtherGolemsTaskDefinition
from golem.task.TaskState import TaskStatus
from examples.gnr.TaskState import RenderingTaskState
from golem.task.TaskBase import Task
from golem.task.TaskState import TaskState
from golem.Client import GolemClientEventListener
from golem.manager.client.NodesManagerClient import NodesManagerClient
from examples.default.customizers.GNRMainWindowCustomizer import GNRMainWindowCustomizer

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
        self.taskTypes          = {}
        self.testTasks          = {}
        self.customizer         = None
        self.rootPath           = os.getcwd()
        self.nodesManagerClient = None
        self.addNewNodesFunction = lambda x: None
        self.startNodesManagerFunction = lambda: None

    ######################
    def registerGui( self, gui ):
        self.customizer = GNRMainWindowCustomizer( gui, self )

    ######################
    def registerClient( self, client ):
        self.client = client
        self.client.registerListener( GNRClientEventListener( self ) )

    ######################
    def registerStartNewNodeFunction( self, func ):
        self.addNewNodesFunction = func

    def registerStartNodesManagerFunction( self, func ):
        self.startNodesManagerFunction = func

    def startNodesManagerServer( self ):
        self.startNodesManagerFunction()

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
        assert taskId in self.tasks, "ApplicationLogic: task {} not added".format( taskId )

        return self.tasks[ taskId ]

    ######################
    def getTaskTypes( self ):
        return self.taskTypes

    ######################
    def getStatus( self ):
        return self.client.getStatus()

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
    def sendInfoTask( self, iterations, fullTaskTimeout, subtaskTimeout ):
        infoTaskDefinition = InfoTaskDefinition()
        infoTaskDefinition.taskId           = "{}".format( uuid.uuid4() )
        infoTaskDefinition.srcFile          = os.path.join( os.environ.get('GOLEM'), "examples\\tasks\\sendSnapshot.py" )
        infoTaskDefinition.totalSubtasks    = iterations
        infoTaskDefinition.fullTaskTimeout  = fullTaskTimeout
        infoTaskDefinition.subtaskTimeout   = subtaskTimeout
        infoTaskDefinition.managerAddress   = self.client.configDesc.managerAddress
        infoTaskDefinition.managerPort      = self.client.configDesc.managerPort

        taskBuilder = InfoTaskBuilder( self.client.getId(),
                                          infoTaskDefinition,
                                        self.client.getRootPath() )

        task = Task.buildTask(  taskBuilder )
        self.addTaskFromDefinition( infoTaskDefinition )
        self.client.enqueueNewTask( task )

    ######################
    def sendTestTasks( self ):
        path = os.path.join( os.environ.get( 'GOLEM' ), 'save/test')
        files = glob.glob( os.path.join( path, '*.gt' ) )
        tasks = []
        for file in files:
            taskState = RenderingTaskState()
            taskState.status = TaskStatus.notStarted
            taskState.definition = pickle.loads( open( file, 'r' ).read() )
            import uuid
            taskState.definition.taskId = "{}".format( uuid.uuid4() )
            tasks.append( taskState )
        self.addTasks ( tasks )
        for task in tasks:
            self.startTask( task.definition.taskId )

    ######################
    def startTask( self, taskId ):
        ts = self.getTask( taskId )

        if ts.taskState.status != TaskStatus.notStarted:
            errorMsg = "Task already started"
            self.__showErrorWindow( errorMsg )
            logger.error( errorMsg )
            return

        tb = self.taskTypes[ ts.definition.taskType.name ].taskBuilderType( self.client.getId(), ts.definition, self.client.getRootPath( ) )

        t = Task.buildTask( tb )

        self.client.enqueueNewTask( t )

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
    def updateOtherGolems( self, golemDir ):
        taskDefinition         = UpdateOtherGolemsTaskDefinition()
        taskDefinition.taskId  = "{}".format( uuid.uuid4() )
        taskDefinition.srcFile          = os.path.join( os.environ.get('GOLEM'), "examples\\tasks\\updateGolem.py" )
        taskDefinition.totalSubtasks    = 100
        taskDefinition.fullTaskTimeout  = 4 * 60 * 60
        taskDefinition.subtaskTimeout   = 20 * 60

        taskBuilder = UpdateOtherGolemsTaskBuilder( self.client.getId(),
                                          taskDefinition,
                                        self.client.getRootPath(), golemDir )

        task = Task.buildTask(  taskBuilder )
        self.addTaskFromDefinition( taskDefinition )
        self.client.enqueueNewTask( task )

        print "Update with {}".format( golemDir )

    ######################
    def changeTask (self, taskId ):
        self.customizer.showChangeTaskDialog( taskId )

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
        taskState = RenderingTaskState()
        taskState.status = TaskStatus.notStarted

        taskState.definition = definition

        self.addTasks( [taskState] )

    ######################
    def addTasks( self, tasks ):

        if len( tasks ) == 0:
            return

        for t in tasks:
            assert isinstance( t, RenderingTaskState )
            if hasattr( t.definition, 'renderer' ):
                t.definition.taskType = self.taskTypes[ t.definition.renderer ]
            if t.definition.taskId not in self.tasks:
                self.tasks[ t.definition.taskId ] = t
                self.customizer.addTask( t )
            else:
                self.tasks[ t.definition.taskId ] = t

        self.customizer.updateTasks( self.tasks )

    ######################
    def saveTask( self, taskState, filePath ):
        f = open( filePath, "wb" )

        tspickled = pickle.dumps( taskState )

        f.write( tspickled )
        f.close()

    ######################
    def registerNewTaskType(self, taskType):
        if taskType.name not in self.taskTypes:
            self.taskTypes[ taskType.name ] = taskType
        else:
            assert False, "Task type {} already registered".format( taskType.name )

    ######################
    def recountPerformance( self, numCores ):
        testFile = os.path.join( os.environ.get('GOLEM'), 'testtasks\minilight\cornellbox.ml.txt')
        resultFile = os.path.join( os.environ.get( 'GOLEM' ), 'examples\\gnr\\node_data\\minilight.ini')
        estimatedPerf =  makePerfTest(testFile, resultFile, numCores)
        return estimatedPerf

    ######################
    def getEnvironments( self ) :
        return self.client.getEnvironments()

    ######################
    def __testTaskComputationFinished( self, success, estMem = 0 ):
        if success:
            self.progressDialog.showMessage("Test task computation success!")
        else:
            self.progressDialog.showMessage("Task test computation failure... Check resources.")
        if self.customizer.newTaskDialogCustomizer:
            self.customizer.newTaskDialogCustomizer.testTaskComputationFinished( success, estMem )

    ######################
    def taskStatusChanged( self, taskId ):

        if taskId in self.tasks:
            assert isinstance( self.tasks[ taskId ], RenderingTaskState )
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
    def __showErrorWindow( self, text ):
        from PyQt4.QtGui import QMessageBox
        msBox = QMessageBox( QMessageBox.Critical, "Error", text )
        msBox.exec_()
        msBox.show()
