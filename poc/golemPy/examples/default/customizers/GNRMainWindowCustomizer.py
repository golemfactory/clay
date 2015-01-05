import os
import cPickle as pickle
import datetime
from PyQt4 import QtCore
from PyQt4.QtGui import QPixmap, QTreeWidgetItem, QMenu, QFileDialog, QMessageBox, QPalette, QPainter, QBrush, QColor, QPen

from examples.default.ui.MainWindow import GNRMainWindow
from examples.gnr.ui.NewTaskDialog import NewTaskDialog
from examples.gnr.ui.ShowTaskResourcesDialog import ShowTaskResourcesDialog
from examples.gnr.ui.TaskDetailsDialog import TaskDetailsDialog
from examples.gnr.ui.SubtaskDetailsDialog import SubtaskDetailsDialog
from examples.gnr.ui.TaskTableElem import TaskTableElem
from examples.gnr.ui.ConfigurationDialog import ConfigurationDialog
from examples.gnr.ui.StatusWindow import StatusWindow
from examples.gnr.ui.ChangeTaskDialog import ChangeTaskDialog
from examples.gnr.ui.InfoTaskDialog import InfoTaskDialog
from examples.gnr.ui.EnvironmentsDialog import EnvironmentsDialog
from examples.gnr.ui.UpdateOtherGolemsDialog import UpdateOtherGolemsDialog
from examples.gnr.RenderingDirManager import getPreviewFile

from examples.default.customizers.NewTaskDialogCustomizer import NewTaskDialogCustomizer
from examples.gnr.customizers.TaskContexMenuCustomizer import TaskContextMenuCustomizer
from examples.gnr.customizers.TaskDetailsDialogCustomizer import TaskDetailsDialogCustomizer
from examples.gnr.customizers.SubtaskDetailsDialogCustomizer import SubtaskDetailsDialogCustomizer
from examples.gnr.customizers.ConfigurationDialogCustomizer import ConfigurationDialogCustomizer
from examples.gnr.customizers.StatusWindowCustomizer import StatusWindowCustomizer
from examples.gnr.customizers.ChangeTaskDialogCustomizer import ChangeTaskDialogCustomizer
from examples.gnr.customizers.InfoTaskDialogCustomizer import InfoTaskDialogCustomizer
from examples.gnr.customizers.EnvironmentsDialogCustomizer import EnvironmentsDialogCustomizer
from examples.gnr.customizers.UpdateOtherGolemsDialogCustomizer import UpdateOtherGolemsDialogCustomizer
from examples.gnr.customizers.MemoryHelper import resourceSizeToDisplay, translateResourceIndex

from golem.task.TaskState import SubtaskStatus

import time
import logging

logger = logging.getLogger(__name__)

class GNRMainWindowCustomizer:
    ############################
    def __init__( self, gui, logic ):

        assert isinstance( gui, GNRMainWindow )

        self.gui    = gui
        self.logic  = logic

        self.__setupConnections()
        self.currentTaskHighlighted         = None
        self.taskDetailsDialog              = None
        self.taskDetailsDialogCustomizer    = None

        palette = QPalette()
        palette.setColor( QPalette.Foreground, QtCore.Qt.red )
        self.gui.ui.errorLabel.setPalette( palette )

    #############################
    def __setupConnections( self ):
        self.gui.ui.actionNew.triggered.connect( self.__showNewTaskDialogClicked )
        self.gui.ui.actionLoadTask.triggered.connect( self.__loadTaskButtonClicked )
        self.gui.ui.actionEdit.triggered.connect( self.__showConfigurationDialogClicked )
        self.gui.ui.actionStatus.triggered.connect( self.__showStatusClicked )
        self.gui.ui.actionStartNodesManager.triggered.connect( self.__startNodesManager )
        self.gui.ui.actionSendInfoTask.triggered.connect( self.__showInfoTaskDialog )
        self.gui.ui.actionSendTestTasks.triggered.connect( self.__sendTestTasks )
        self.gui.ui.actionUpdateOtherGolems.triggered.connect( self.__sendUpdateOtherGolemsTask )
        self.gui.ui.actionEnvironments.triggered.connect( self.__showEnvironments )
        QtCore.QObject.connect( self.gui.ui.taskTableWidget, QtCore.SIGNAL( "cellClicked(int, int)" ), self.__taskTableRowClicked )
        QtCore.QObject.connect( self.gui.ui.taskTableWidget, QtCore.SIGNAL( "doubleClicked(const QModelIndex)" ), self.__taskTableRowDoubleClicked )
        self.gui.ui.taskTableWidget.customContextMenuRequested.connect( self.__contexMenuRequested )

    ############################
    # Add new task to golem client
    def enqueueNewTask( self, uiNewTaskInfo ):
        self.logic.enqueueNewTask( uiNewTaskInfo )

    ############################
    # Updates tasks information in gui
    def updateTasks( self, tasks ):
        for i in range( self.gui.ui.taskTableWidget.rowCount() ):
            taskId = self.gui.ui.taskTableWidget.item( i, 0 ).text()
            taskId = "{}".format( taskId )
            if taskId in tasks:
                self.gui.ui.taskTableWidget.item( i, 1 ).setText( tasks[ taskId ].taskState.status )
                progressBarInBoxLayout = self.gui.ui.taskTableWidget.cellWidget( i, 2 )
                layout = progressBarInBoxLayout.layout()
                pb = layout.itemAt( 0 ).widget()
                pb.setProperty( "value", int( tasks[ taskId ].taskState.progress * 100.0 ) )
                if self.taskDetailsDialogCustomizer:
                    if self.taskDetailsDialogCustomizer.gnrTaskState.definition.taskId == taskId:
                        self.taskDetailsDialogCustomizer.updateView( tasks[ taskId ].taskState )

            else:
                assert False, "Trying to update not added task."
        
    ############################
    # Add task information in gui
    def addTask( self, task ):
        self.__addTask( task.definition.taskId, task.status )

    ############################
    def updateTaskAdditionalInfo( self, t ):
        self.currentTaskHighlighted = t

    ############################
    def __addTask( self, taskId, status ):
        currentRowCount = self.gui.ui.taskTableWidget.rowCount()
        self.gui.ui.taskTableWidget.insertRow( currentRowCount )

        taskTableElem = TaskTableElem( taskId, status )

        for col in range( 0, 2 ): self.gui.ui.taskTableWidget.setItem( currentRowCount, col, taskTableElem.getColumnItem( col ) )

        self.gui.ui.taskTableWidget.setCellWidget( currentRowCount, 2, taskTableElem.progressBarInBoxLayoutWidget )

        self.gui.ui.taskTableWidget.setCurrentItem( self.gui.ui.taskTableWidget.item( currentRowCount, 1) )
        self.updateTaskAdditionalInfo( self.logic.getTask( taskId ) )

    ############################
    def removeTask( self, taskId ):

        for row in range(0, self.gui.ui.taskTableWidget.rowCount()):
            if self.gui.ui.taskTableWidget.item(row, 0).text() == taskId:
                self.gui.ui.taskTableWidget.removeRow( row )
                self.currentTaskHighlighted = None
                return


    ############################
    def __loadTaskButtonClicked( self ):
        golemPath = os.environ.get( 'GOLEM' )
        dir = ""
        if golemPath:
            saveDir = os.path.join( golemPath, "save" )
            if os.path.isdir( saveDir ):
                dir = saveDir

        fileName = QFileDialog.getOpenFileName( self.gui.window,
            "Choose task file", dir, "Golem Task (*.gt)")
        if os.path.exists( fileName ):
            self.__loadTask( fileName )

    ############################
    def __startNodesManager( self ):
        self.logic.startNodesManagerServer()

    ############################
    def __sendInfoTask( self ):
        self.logic.sendInfoTask()

    ############################
    def __sendTestTasks( self ):
        self.logic.sendTestTasks()

    def __sendUpdateOtherGolemsTask( self ):
        updateOtherGolemsDialog = UpdateOtherGolemsDialog ( self.gui.window )
        updateOtherGolemsDialogCustomizer = UpdateOtherGolemsDialogCustomizer( updateOtherGolemsDialog, self.logic )
        updateOtherGolemsDialog.show()


    ############################
    def __loadTask( self, filePath ):
        f = open( filePath, 'r' )

        try:
            definition = pickle.loads( f.read() )
        except Exception, e:
            definition = None
            logger.error("Can't unpickle the file {}: {}".format( filePath, str( e ) ) )
            QMessageBox().critical(None, "Error", "This is not a proper gt file")
        finally:
            f.close()

        if definition:
            self.newTaskDialog = NewTaskDialog( self.gui.window )

            self.newTaskDialogCustomizer = NewTaskDialogCustomizer( self.newTaskDialog, self.logic )

            self.newTaskDialogCustomizer.loadTaskDefinition( definition )

            self.newTaskDialog.show()

    ############################
    def __showTaskContextMenu( self, p ):

        if self.gui.ui.taskTableWidget.itemAt( p ) is None:
            return
        row = self.gui.ui.taskTableWidget.itemAt( p ).row()

        idItem = self.gui.ui.taskTableWidget.item( row, 0 )

        taskId = "{}".format( idItem.text() )

        gnrTaskState = self.logic.getTask( taskId )

        menu = QMenu()

        self.taskContextMenuCustomizer =  TaskContextMenuCustomizer( menu, self.logic, gnrTaskState )

        menu.popup( self.gui.ui.taskTableWidget.viewport().mapToGlobal( p ) )
        menu.exec_()

    # SLOTS
    #############################
    def __taskTableRowClicked( self, row, col ):
        if row < self.gui.ui.taskTableWidget.rowCount():
            taskId = self.gui.ui.taskTableWidget.item( row, 0 ).text()
            taskId = "{}".format( taskId )
            t = self.logic.getTask( taskId )
            self.updateTaskAdditionalInfo( t )

    #############################
    def showDetailsDialog(self, taskId):
        ts = self.logic.getTask( taskId )
        self.taskDetailsDialog = TaskDetailsDialog( self.gui.window )
        self.taskDetailsDialogCustomizer = TaskDetailsDialogCustomizer( self.taskDetailsDialog, self.logic, ts )
        self.taskDetailsDialog.show()

    #############################
    def showSubtaskDetailsDialog( self, subtask ):
        subtaskDetailsDialog = SubtaskDetailsDialog( self.gui.window )
        subtaskDetailsDialogCustomizer = SubtaskDetailsDialogCustomizer( subtaskDetailsDialog, self.logic, subtask )
        subtaskDetailsDialog.show()

    #############################
    def __taskTableRowDoubleClicked( self, m ):
        row = m.row()
        taskId = "{}".format( self.gui.ui.taskTableWidget.item( row, 0 ).text() )
        self.showDetailsDialog(taskId)

    #############################
    def showNewTaskDialog(self, taskId):
        ts = self.logic.getTask( taskId )
        self.newTaskDialog = NewTaskDialog( self.gui.window )
        self.newTaskDialogCustomizer = NewTaskDialogCustomizer ( self.newTaskDialog, self.logic )
        self.newTaskDialogCustomizer.loadTaskDefinition(ts.definition)
        self.newTaskDialog.show()

    def __showNewTaskDialogClicked( self ):
        self.newTaskDialog = NewTaskDialog( self.gui.window )

        self.newTaskDialogCustomizer = NewTaskDialogCustomizer( self.newTaskDialog, self.logic )
        self.newTaskDialog.show()

    #############################
    def __showInfoTaskDialog( self ):
        self.infoTaskDialog = InfoTaskDialog( self.gui.window )
        self.infoTaskDialogCustomizer = InfoTaskDialogCustomizer( self.infoTaskDialog, self.logic )
     #   self.infoTaskDialogCustomizer.loadDefaults()
        self.infoTaskDialog.show()

    #############################
    def showChangeTaskDialog(self, taskId ):

        self.changeTaskDialog = ChangeTaskDialog( self.gui.window )
        self.changeTaskDialogCustomizer = ChangeTaskDialogCustomizer( self.changeTaskDialog, self.logic )
        ts = self.logic.getTask( taskId )
        self.changeTaskDialogCustomizer.loadTaskDefinition( ts.definition )
        self.changeTaskDialog.show()

    #############################
    def __showStatusClicked( self ):
        self.statusWindow = StatusWindow( self.gui.window )

        self.statusWindowCustomizer = StatusWindowCustomizer( self.statusWindow, self.logic )
        self.statusWindowCustomizer.getStatus()
        self.statusWindow.show()

    ##########################
    def __contexMenuRequested( self, p ):
        self.__showTaskContextMenu( p )

    #############################
    def __showConfigurationDialogClicked( self ):
        self.configurationDialog = ConfigurationDialog( self.gui.window )
        self.configurationDialogCustomizer = ConfigurationDialogCustomizer( self.configurationDialog, self.logic )
        self.configurationDialogCustomizer.loadConfig()
        self.configurationDialog.show()

    #############################
    def __showEnvironments ( self ):
        self.environmentsDialog = EnvironmentsDialog( self.gui.window )

        self.environmentsDialogCustomizer = EnvironmentsDialogCustomizer( self.environmentsDialog, self.logic )
        self.environmentsDialog.show()

#######################################################################################
def insertItem( root, pathTable ):
    assert isinstance( root, QTreeWidgetItem )

    if len( pathTable ) > 0:
        for i in range( root.childCount() ):
            if pathTable[ 0 ] == "{}".format( root.child( i ).text( 0 ) ):
                insertItem( root.child( i ), pathTable[ 1: ] )
                return

        newChild = QTreeWidgetItem( [ pathTable[ 0 ] ] )
        root.addChild( newChild )
        insertItem( newChild, pathTable[ 1: ] )

