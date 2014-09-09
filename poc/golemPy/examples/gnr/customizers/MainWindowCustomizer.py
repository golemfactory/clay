import os
import cPickle as pickle
import datetime
from PyQt4 import QtCore
from PyQt4.QtGui import QPixmap, QTreeWidgetItem, QMenu, QFileDialog, QMessageBox

from examples.gnr.ui.MainWindow import GNRMainWindow
from examples.gnr.ui.NewTaskDialog import NewTaskDialog
from examples.gnr.ui.ShowTaskResourcesDialog import ShowTaskResourcesDialog
from examples.gnr.ui.TaskDetailsDialog import TaskDetailsDialog
from examples.gnr.ui.TaskTableElem import TaskTableElem
from examples.gnr.ui.ConfigurationDialog import ConfigurationDialog
from examples.gnr.ui.StatusWindow import StatusWindow
from examples.gnr.ui.ChangeTaskDialog import ChangeTaskDialog

from NewTaskDialogCustomizer import NewTaskDialogCustomizer
from TaskContexMenuCustomizer import TaskContextMenuCustomizer
from TaskDetailsDialogCustomizer import TaskDetailsDialogCustomizer
from ConfigurationDialogCustomizer import ConfigurationDialogCustomizer
from StatusWindowCustomizer import StatusWindowCustomizer
from ChangeTaskDialogCustomizer import ChangeTaskDialogCustomizer

import time
import logging

logger = logging.getLogger(__name__)

class MainWindowCustomizer:
    ############################
    def __init__( self, gui, logic ):

        assert isinstance( gui, GNRMainWindow )

        self.gui    = gui
        self.logic  = logic

        self.__setupConnections()
        self.currentTaskHighlighted         = None
        self.taskDetailsDialog              = None
        self.taskDetailsDialogCustomizer    = None

    #############################
    def __setupConnections( self ):
        self.gui.ui.actionNew.triggered.connect( self.__showNewTaskDialogClicked )
        self.gui.ui.actionLoadTask.triggered.connect( self.__loadTaskButtonClicked )
        self.gui.ui.actionEdit.triggered.connect( self.__showConfigurationDialogClicked )
        self.gui.ui.actionStatus.triggered.connect( self.__showStatusClicked )
        QtCore.QObject.connect( self.gui.ui.renderTaskTableWidget, QtCore.SIGNAL( "cellClicked(int, int)" ), self.__taskTableRowClicked )
        QtCore.QObject.connect( self.gui.ui.renderTaskTableWidget, QtCore.SIGNAL( "doubleClicked(const QModelIndex)" ), self.__taskTableRowDoubleClicked )
        self.gui.ui.showResourceButton.clicked.connect( self.__showTaskResourcesClicked )
        self.gui.ui.renderTaskTableWidget.customContextMenuRequested.connect( self.__contexMenuRequested )

    ############################
    # Add new task to golem client
    def enqueueNewTask( self, uiNewTaskInfo ):
        self.logic.enqueueNewTask( uiNewTaskInfo )

    ############################
    # Updates tasks information in gui
    def updateTasks( self, tasks ):
        for i in range( self.gui.ui.renderTaskTableWidget.rowCount() ):
            taskID = self.gui.ui.renderTaskTableWidget.item( i, 0 ).text()
            taskID = "{}".format( taskID )
            if taskID in tasks:
                self.gui.ui.renderTaskTableWidget.item( i, 1 ).setText( tasks[ taskID ].taskState.status )
                progressBarInBoxLayout = self.gui.ui.renderTaskTableWidget.cellWidget( i, 2 )
                layout = progressBarInBoxLayout.layout()
                pb = layout.itemAt( 0 ).widget()
                pb.setProperty( "value", int( tasks[ taskID ].taskState.progress * 100.0 ) )
                if self.taskDetailsDialogCustomizer:
                    if self.taskDetailsDialogCustomizer.gnrTaskState.definition.id == taskID:
                        self.taskDetailsDialogCustomizer.updateView( tasks[ taskID ].taskState )
            else:
                assert False, "Trying to update not added task."
        
    ############################
    # Add task information in gui
    def addTask( self, task ):
        self.__addTask( task.definition.id, task.status )

    ############################
    def updateTaskAdditionalInfo( self, t ):
        from examples.gnr.TaskState import GNRTaskState
        assert isinstance( t, GNRTaskState )

        self.gui.ui.minNodePower.setText( "{} ray per pixel".format( t.definition.minPower ) )
        self.gui.ui.minSubtask.setText( "{} pixels".format( t.definition.minSubtask ) )
        self.gui.ui.maxSubtask.setText( "{} pixels".format( t.definition.maxSubtask ) )
        self.gui.ui.subtaskTimeout.setText( "{} minutes".format( int( t.definition.subtaskTimeout / 60.0 ) ) )
        self.gui.ui.resolution.setText( "{} x {}".format( t.definition.resolution[ 0 ], t.definition.resolution[ 1 ] ) )
        self.gui.ui.renderer.setText( "{}".format( t.definition.renderer ) )
        self.gui.ui.algorithmType.setText( "{}".format( t.definition.algorithmType ) )
        self.gui.ui.pixelFilter.setText( "{}".format( t.definition.pixelFilter ) )
        self.gui.ui.samplesPerPixel.setText( "{}".format( t.definition.samplesPerPixelCount ) )
        self.gui.ui.outputFile.setText( u"{}".format( t.definition.outputFile ) )
        self.gui.ui.fullTaskTimeout.setText( str( datetime.timedelta( seconds = t.definition.fullTaskTimeout ) ) )
        if t.taskState.timeStarted != 0.0:
            lt = time.localtime( t.taskState.timeStarted )
            timeString  = time.strftime( "%Y.%m.%d  %H:%M:%S", lt )
            self.gui.ui.timeStarted.setText( timeString )

        if t.taskState.resultPreview:
            filePath = os.path.abspath( t.taskState.resultPreview )
            if os.path.exists( filePath ):
                self.gui.ui.previewLabel.setPixmap( QPixmap( filePath ) )
        else:
            self.gui.ui.previewLabel.setPixmap( QPixmap( "ui/nopreview.jpg" ) )

        self.currentTaskHighlighted = t

    ############################
    def __addTask( self, id, status ):
        currentRowCount = self.gui.ui.renderTaskTableWidget.rowCount()
        self.gui.ui.renderTaskTableWidget.insertRow( currentRowCount )

        taskTableElem = TaskTableElem( id, status )

        for col in range( 0, 2 ): self.gui.ui.renderTaskTableWidget.setItem( currentRowCount, col, taskTableElem.getColumnItem( col ) )

        self.gui.ui.renderTaskTableWidget.setCellWidget( currentRowCount, 2, taskTableElem.progressBarInBoxLayoutWidget )

        self.updateTaskAdditionalInfo( self.logic.getTask( id ) )

    ############################
    def removeTask( self, id ):

        for row in range(0, self.gui.ui.renderTaskTableWidget.rowCount()):
            if self.gui.ui.renderTaskTableWidget.item(row, 0).text() == id:
                self.gui.ui.renderTaskTableWidget.removeRow( row )
                return

    ############################
    def __loadTaskButtonClicked( self ):
        fileName = QFileDialog.getOpenFileName( self.gui.window,
            "Choose task file", "", "Golem Task (*.gt)")
        if os.path.exists( fileName ):
            self.__loadTask( fileName )

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

        if self.gui.ui.renderTaskTableWidget.itemAt( p ) is None:
            return
        row = self.gui.ui.renderTaskTableWidget.itemAt( p ).row()

        idItem = self.gui.ui.renderTaskTableWidget.item( row, 0 )

        taskId = "{}".format( idItem.text() )

        gnrTaskState = self.logic.getTask( taskId )

        menu = QMenu()

        self.taskContextMenuCustomizer =  TaskContextMenuCustomizer( menu, self.logic, gnrTaskState )

        menu.popup( self.gui.ui.renderTaskTableWidget.viewport().mapToGlobal( p ) )
        menu.exec_()

    # SLOTS
    #############################
    def __taskTableRowClicked( self, row, col ):
        if row < self.gui.ui.renderTaskTableWidget.rowCount():
            taskId = self.gui.ui.renderTaskTableWidget.item( row, 0 ).text()
            taskId = "{}".format( taskId )
            t = self.logic.getTask( taskId )
            self.updateTaskAdditionalInfo( t )

    #############################
    def showDetailsDialog(self, taskId):
        ts = self.logic.getTask( taskId )
        self.taskDetailsDialog = TaskDetailsDialog( self.gui.window )
        self.taskDetailsDialogCustomizer = TaskDetailsDialogCustomizer( self.taskDetailsDialog, self.logic, ts )
        self.taskDetailsDialog.show()


    def __taskTableRowDoubleClicked( self, m ):
        row = m.row()
        taskId = "{}".format( self.gui.ui.renderTaskTableWidget.item( row, 0 ).text() )
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

    #############################
    def __showTaskResourcesClicked( self ):

        if self.currentTaskHighlighted:

            res = list( self.currentTaskHighlighted.definition.resources )

            for i in range( len( res ) ):
                res[ i ] = os.path.abspath( res[ i ] )

            res.sort()

            self.showTaskResourcesDialog = ShowTaskResourcesDialog( self.gui.window )

            item = QTreeWidgetItem( ["Resources"] )
            self.showTaskResourcesDialog.ui.folderTreeWidget.insertTopLevelItem( 0, item )

            self.showTaskResourcesDialog.ui.closeButton.clicked.connect( self.__showTaskResCloseButtonClicked )

            for r in res:
                splited = r.split("\\")

                insertItem( item, splited )

            self.showTaskResourcesDialog.ui.mainSceneFileLabel.setText( self.currentTaskHighlighted.definition.mainSceneFile )
            self.showTaskResourcesDialog.ui.folderTreeWidget.expandAll()

            self.showTaskResourcesDialog.show()

    #############################
    def __showTaskResCloseButtonClicked( self ):
        self.showTaskResourcesDialog.window.close()

    ##########################
    def __contexMenuRequested( self, p ):
        self.__showTaskContextMenu( p )

    #############################
    def __showConfigurationDialogClicked( self ):
        self.configurationDialog = ConfigurationDialog( self.gui.window )
        self.configurationDialogCustomizer = ConfigurationDialogCustomizer( self.configurationDialog, self.logic )
        self.configurationDialogCustomizer.loadConfig()
        self.configurationDialog.show()

#######################################################################################
def insertItem( root, pathTable ):
    assert isinstance( root, QTreeWidgetItem )

    found = False

    if len( pathTable ) > 0:
        for i in range( root.childCount() ):
            if pathTable[ 0 ] == "{}".format( root.child( i ).text( 0 ) ):
                insertItem( root.child( i ), pathTable[ 1: ] )
                return

        newChild = QTreeWidgetItem( [ pathTable[ 0 ] ] )
        root.addChild( newChild )
        insertItem( newChild, pathTable[ 1: ] )




