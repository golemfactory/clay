import os

from PyQt4 import QtCore

from examples.gnr.ui.TestingTaskProgressDialog import TestingTaskProgressDialog
from golem.task.TaskState import TaskStatus
from examples.gnr.TaskState import GNRTaskState
from examples.gnr.task.TaskTester import TaskTester
from golem.task.TaskBase import Task
from golem.task.TaskState import TaskState
from golem.Client import GolemClientEventListener
from customizers.MainWindowCustomizer import MainWindowCustomizer


class GNRClientEventListener( GolemClientEventListener ):
    #####################
    def __init__( self, logic ):
        self.logic = logic
        GolemClientEventListener.__init__( self )

    #####################
    def taskUpdated( self, taskId ):
        self.logic.taskStatusChanged( taskId )


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

    ######################
    def registerGui( self, gui ):
        self.customizer = MainWindowCustomizer( gui, self )

    ######################
    def registerClient( self, client ):
        self.client = client
        self.client.registerListener( GNRClientEventListener( self ) )

    ######################
    def getTask( self, id ):
        assert id in self.tasks, "GNRApplicationLogic: task {} not added".format( id )

        return self.tasks[ id ]

    ######################
    def getRenderers( self ):
        return self.renderers

    ######################
    def getRenderer( self, name ):
        if name in self.renderers:
            return self.renderers[ name ]
        else:
            assert False, "Renderer {} not registered".format( name )

    ######################
    def startTask( self, taskId ):
        ts = self.getTask( taskId )

        assert ts.status == TaskStatus.notStarted # TODO:

        tb = self.renderers[ ts.definition.renderer ].taskBuilderType( self.client.getId(), ts.definition )

        t = Task.buildTask( tb )

        self.client.enqueueNewTask( t )

    ######################
    def getDefaultRenderer( self ):
        return self.defaultRenderer

    ######################
    def getTestTasks( self ):
        return self.testTasks

    ######################
    def addTasks( self, tasks ):

        if len( tasks ) == 0:
            return

        for t in tasks:
            print t.__class__
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
    def runTestTask( self, taskState ):
        if self.__validateTaskState( taskState ):

            tb = self.renderers[ taskState.definition.renderer ].taskBuilderType( self.client.getId(), taskState.definition )

            t = Task.buildTask( tb )

            self.tt = TaskTester( t, self.__testTaskComputationFinished )

            self.progressDialog = TestingTaskProgressDialog( None, self.tt )

            self.progressDialog.show()

            self.tt.run()

            return True
        else:
            return False

    ######################
    def __testTaskComputationFinished( self, success ):
        self.progressDialog.setProgress( 100 )
        self.progressDialog.close()
        self.progressDialog = None
        if self.customizer.newTaskDialogCustomizer:
            self.customizer.newTaskDialogCustomizer.testTaskComputationFinished( success )

    ######################
    def taskStatusChanged( self, taskId ):

        if taskId in self.tasks:
            t = self.tasks[ taskId ]
            assert isinstance( t, GNRTaskState )
            ts = self.client.quarryTaskState( taskId )
            assert isinstance( ts, TaskState )
            t.taskState = ts
            self.customizer.updateTasks( self.tasks )
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
    def __validateTaskState( self, taskState ):

        td = taskState.definition
        if td.renderer in self.renderers:
            r = self.renderers[ td.renderer ]

            if not os.path.exists( td.mainProgramFile ):
                self.__showErrorWindow( "Main program file does not exist: {}".format( td.mainProgramFile ) )
                return False

            if len( td.outputFile ) == 0: # FIXME
                self.__showErrorWindow( "Output file is not properly set" )
                return False

            if not os.path.exists( td.mainSceneFile ):
                self.__showErrorWindow( "Main scene file is not properly set" )
                return False


        else:
            return False

        return True

