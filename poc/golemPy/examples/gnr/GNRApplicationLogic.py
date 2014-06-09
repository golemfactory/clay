from customizers.MainWindowCustomizer import MainWindowCustomizer

import os

from TaskState import TaskStatus
from PyQt4 import QtCore

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

        self.emit( QtCore.SIGNAL( "taskStartingRequested(QObject)" ), ts )

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
            return True
        else:
            return False

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
                self.__showErrorWindow( "Output file is not set" )
                return False

        else:
            return False

        return True

