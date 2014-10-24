import os
import logging
import cPickle as pickle
from PyQt4 import QtCore

from examples.gnr.task.InfoTask import InfoTaskBuilder
from examples.gnr.ui.TestingTaskProgressDialog import TestingTaskProgressDialog
from golem.task.TaskState import TaskStatus
from examples.gnr.TaskState import GNRTaskState, TaskDefinition
from examples.gnr.task.TaskTester import TaskTester
from golem.task.TaskBase import Task
from golem.task.TaskState import TaskState
from golem.Client import GolemClientEventListener
from golem.manager.client.NodesManagerClient import NodesManagerUidClient
from customizers.MainWindowCustomizer import MainWindowCustomizer

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

taskToRemoveStatus = [ TaskStatus.aborted, TaskStatus.failure, TaskStatus.finished, TaskStatus.paused ]

class GNRApplicationLogic( QtCore.QObject ):
    ######################
    def __init__( self ):
        QtCore.QObject.__init__( self )
        self.tasks              = {}
        self.renderers          = {}
        self.testTasks          = {}
        self.customizer         = None
        self.currentRenderer    = None
        self.defaultRenderer    = None
        self.rootPath           = os.getcwd()
        self.nodesManagerClient = None
        self.addNewNodesFunction = lambda x: None
        self.startNodesManagerFunction = lambda: None

    ######################
    def registerGui( self, gui ):
        self.customizer = MainWindowCustomizer( gui, self )

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
    def getTask( self, id ):
        assert id in self.tasks, "GNRApplicationLogic: task {} not added".format( id )

        return self.tasks[ id ]

    ######################
    def getRenderers( self ):
        return self.renderers

    ######################
    def getStatus( self ):
        return self.client.getStatus()


    ######################
    def getConfig( self ):
        return self.client.configDesc

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
    def getRenderer( self, name ):
        if name in self.renderers:
            return self.renderers[ name ]
        else:
            assert False, "Renderer {} not registered".format( name )

    ######################
    #FIXME: task definiton jest skoncentrowany na taskach PBRT, trzeba zrobic tu jakis innych mechanizm definiowania definicji taskow
    def sendInfoTask( self, iterations, fullTaskTimeout, subtaskTimeout ):
        taskBuilder = InfoTaskBuilder( self.client.getId(),
                                          "sendSnapshot.py",
                                          self.client.configDesc.managerAddress,
                                          self.client.configDesc.managerPort,
                                          iterations,
                                          fullTaskTimeout,
                                          subtaskTimeout)
        task = Task.buildTask(  taskBuilder )
        taskDefinition = TaskDefinition()
        taskDefinition.id = task.header.taskId
        taskDefinition.taskResources = task.taskResources
        self.addTaskFromDefinition( taskDefinition )
        self.client.enqueueNewTask( task )

    ######################
    def startTask( self, taskId ):
        ts = self.getTask( taskId )

        assert ts.taskState.status == TaskStatus.notStarted # TODO:

        tb = self.renderers[ ts.definition.renderer ].taskBuilderType( self.client.getId(), ts.definition, self.client.getRootPath( ) )

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
    def getDefaultRenderer( self ):
        return self.defaultRenderer

    ######################
    def getTestTasks( self ):
        return self.testTasks

    ######################
    def addTaskFromDefinition ( self, definition ):
        taskState = GNRTaskState()
        taskState.status = TaskStatus.notStarted

        taskState.definition = definition

        self.addTasks( [taskState] )


    ######################
    def addTasks( self, tasks ):

        if len( tasks ) == 0:
            return

        for t in tasks:
            assert isinstance( t, GNRTaskState )
            if t.definition.id not in self.tasks:
                self.tasks[ t.definition.id ] = t
                self.customizer.addTask( t )
            else:
                self.tasks[ t.definition.id ] = t

        self.customizer.updateTasks( self.tasks )

    ######################
    def registerNewRendererType( self, renderer ):
        if renderer.name not in self.renderers:
            self.renderers[ renderer.name ] = renderer
            if len( self.renderers ) == 1:
                self.defaultRenderer = renderer
        else:
            assert False, "Renderer {} already registered".format( renderer.name )

    ######################
    def registerNewTestTaskType( self, testTaskInfo ):
        if testTaskInfo.name not in self.testTasks:
            self.testTasks[ testTaskInfo.name ] = testTaskInfo
        else:
            assert False, "Test task {} already registered".format( testTaskInfo.name )

    ######################
    def setCurrentRenderer( self, rname ):
        if rname in self.renderers:
            self.currentRenderer = self.renderers[ rname ]
        else:
            assert False, "Unreachable"

    ######################
    def getCurrentRenderer( self ):
        return self.currentRenderer

    ######################
    def saveTask( self, taskState, filePath ):
        f = open( filePath, "wb" )

        tspickled = pickle.dumps( taskState )

        f.write( tspickled )
        f.close()

    ######################
    def recountPerformance( self, numCores ):
        testFile =  os.path.abspath( os.path.join( self.rootPath, "..\\..\\testtasks\\minilight\\cornellbox.ml.txt"))
        resultFile = os.path.abspath( os.path.join( self.rootPath, "node_data\\minilight.ini" ))
        estimatedPerf =  makePerfTest(testFile, resultFile, numCores)
        return estimatedPerf


    ######################
    def runTestTask( self, taskState ):
        if self.__validateTaskState( taskState ):

            tb = self.renderers[ taskState.definition.renderer ].taskBuilderType( self.client.getId(), taskState.definition, self.client.getRootPath() )

            t = Task.buildTask( tb )

            self.tt = TaskTester( t, self.client.getRootPath(), self.__testTaskComputationFinished )

            self.progressDialog = TestingTaskProgressDialog( self.customizer.gui.window  )
            self.progressDialog.show()

            self.tt.run()

            return True
        else:
            return False

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
            assert isinstance( self.tasks[ taskId ], GNRTaskState )
            ts = self.client.querryTaskState( taskId )
            assert isinstance( ts, TaskState )
            self.tasks[taskId].taskState = ts
            self.customizer.updateTasks( self.tasks )
            if ts.status in taskToRemoveStatus:
                self.client.taskServer.removeTaskHeader( taskId )
                self.client.p2pservice.removeTask( taskId )
        else:
            assert False, "Should never be here!"


        if self.customizer.currentTaskHighlighted.definition.id == taskId:
            self.customizer.updateTaskAdditionalInfo( self.tasks[ taskId ] )

    ######################
    def __showErrorWindow( self, text ):
        from PyQt4.QtGui import QMessageBox
        msBox = QMessageBox( QMessageBox.Critical, "Error", text )
        msBox.exec_()
        msBox.show()

    ######################
    def __checkOutputFile(self, outputFile):
        try:
            if os.path.exists( outputFile ):
                f = open( outputFile , 'a')
                f.close()
            else:
                f = open( outputFile , 'w')
                f.close()
                os.remove(outputFile)
            return True
        except IOError:
            self.__showErrorWindow( "Cannot open file: {}".format( outputFile ))
            return False
        except:
            self.__showErrorWindow( "Output file is not properly set" )
            return False

    ######################
    def __validateTaskState( self, taskState ):

        td = taskState.definition
        if td.renderer in self.renderers:
            r = self.renderers[ td.renderer ]

            if not os.path.exists( td.mainProgramFile ):
                self.__showErrorWindow( "Main program file does not exist: {}".format( td.mainProgramFile ) )
                return False

            if not self.__checkOutputFile(td.outputFile):
                return False

            if not os.path.exists( td.mainSceneFile ):
                self.__showErrorWindow( "Main scene file is not properly set" )
                return False


        else:
            return False

        return True

