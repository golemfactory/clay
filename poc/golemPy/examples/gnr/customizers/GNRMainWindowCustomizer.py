import logging
import os
import cPickle as pickle

from PyQt4 import QtCore
from PyQt4.QtGui import QPalette, QFileDialog, QMessageBox, QMenu

logger = logging.getLogger(__name__)

from examples.gnr.ui.NewTaskDialog import NewTaskDialog
from examples.gnr.ui.TaskTableElem import TaskTableElem
from examples.gnr.ui.TaskDetailsDialog import TaskDetailsDialog
from examples.gnr.ui.SubtaskDetailsDialog import SubtaskDetailsDialog
from examples.gnr.ui.ChangeTaskDialog import ChangeTaskDialog
from examples.gnr.ui.StatusWindow import StatusWindow
from examples.gnr.ui.AboutWindow import AboutWindow
from examples.gnr.ui.ConfigurationDialog import ConfigurationDialog
from examples.gnr.ui.EnvironmentsDialog import EnvironmentsDialog

from examples.gnr.customizers.NewTaskDialogCustomizer import NewTaskDialogCustomizer
from examples.gnr.customizers.TaskContexMenuCustomizer import TaskContextMenuCustomizer
from examples.gnr.customizers.TaskDetailsDialogCustomizer import TaskDetailsDialogCustomizer
from examples.gnr.customizers.SubtaskDetailsDialogCustomizer import SubtaskDetailsDialogCustomizer
from examples.gnr.customizers.ChangeTaskDialogCustomizer import ChangeTaskDialogCustomizer
from examples.gnr.customizers.StatusWindowCustomizer import StatusWindowCustomizer
from examples.gnr.customizers.AboutWindowCustomizer import AboutWindowCustomizer
from examples.gnr.customizers.ConfigurationDialogCustomizer import ConfigurationDialogCustomizer
from examples.gnr.customizers.EnvironmentsDialogCustomizer import EnvironmentsDialogCustomizer

from golem.core.simpleexccmd import isWindows, execCmd

class GNRMainWindowCustomizer:
    ############################
    def __init__( self, gui, logic ):

        self.gui    = gui
        self.logic  = logic

        self.currentTaskHighlighted         = None
        self.taskDetailsDialog              = None
        self.taskDetailsDialogCustomizer    = None
        self.lastDefinition = None

        self._setupConnections()

        self._setErrorLabel()

    #############################
    def _setupConnections( self ):
        self._setupBasicTaskConnections()
        self._setupBasicAppConnections()

    #############################
    def _setupBasicTaskConnections( self ):
        self.gui.ui.actionNew.triggered.connect( self._showNewTaskDialogClicked )
        self.gui.ui.actionLoadTask.triggered.connect( self._loadTaskButtonClicked )
        QtCore.QObject.connect( self.gui.ui.taskTableWidget, QtCore.SIGNAL( "cellClicked(int, int)" ), self._taskTableRowClicked )
        QtCore.QObject.connect( self.gui.ui.taskTableWidget, QtCore.SIGNAL( "doubleClicked(const QModelIndex)" ), self._taskTableRowDoubleClicked )
        self.gui.ui.taskTableWidget.customContextMenuRequested.connect( self._contexMenuRequested )

    #############################
    def _setupBasicAppConnections( self ):
        self.gui.ui.actionEdit.triggered.connect( self._showConfigurationDialogClicked )
        self.gui.ui.actionStatus.triggered.connect( self._showStatusClicked )
        self.gui.ui.actionAbout.triggered.connect( self._showAboutClicked )
        self.gui.ui.actionEnvironments.triggered.connect( self._showEnvironments )

    ############################
    def _setErrorLabel( self ):
        palette = QPalette()
        palette.setColor( QPalette.Foreground, QtCore.Qt.red )
        self.gui.ui.errorLabel.setPalette( palette )

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
                assert False, "Update task for unknown task."

    ############################
    # Add task information in gui
    def addTask( self, task ):
        self._addTask( task.definition.taskId, task.status )

    ############################
    def updateTaskAdditionalInfo( self, t ):
        self.currentTaskHighlighted = t

    #############################
    def showTaskResult( self, taskId ):
        t = self.logic.getTask( taskId )
        if hasattr( t.definition, 'outputFile' ) and os.path.isfile( t.definition.outputFile ):
            self._showFile( t.definition.outputFile )
        elif hasattr( t.definition.options, 'outputFile' ) and os.path.isfile( t.definition.options.outputFile ):
            self._showFile( t.definition.options.outputFile )
        else:
            msgBox = QMessageBox()
            msgBox.setText("No output file defined.")
            msgBox.exec_()

    ############################
    def _showFile( self, fileName ):
        if isWindows():
            os.startfile( fileName )
        else:
            opener = "see"
            execCmd([opener, fileName ], wait=False )


    ############################
    def _addTask( self, taskId, status ):
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
                return

   #############################
    def _showNewTaskDialog(self, definition):
        self._setNewTaskDialog()
        self._setNewTaskDialogCustomizer()
        self.newTaskDialogCustomizer.loadTaskDefinition(definition)
        self.newTaskDialog.show()

   #############################
    def _showNewTaskDialogClicked( self ):
        self._setNewTaskDialog()
        self._setNewTaskDialogCustomizer()
        self.newTaskDialog.show()

    #############################
    def showNewTaskDialog(self, taskId):
        ts = self.logic.getTask( taskId )
        if ts is not None:
            self._showNewTaskDialog( ts.definition )
        else:
            logger.error( "Can't get taski information for task {}".format( taskId ) )

    ############################
    def _setNewTaskDialog( self ):
        self.newTaskDialog = NewTaskDialog( self.gui.window )

    ############################
    def _setNewTaskDialogCustomizer( self ):
        self.newTaskDialogCustomizer = NewTaskDialogCustomizer( self.newTaskDialog, self.logic )


    ############################
    def _loadTaskButtonClicked( self ):
        golemPath = os.environ.get( 'GOLEM' )
        dir = ""
        if golemPath:
            saveDir = os.path.join( golemPath, "save" )
            if os.path.isdir( saveDir ):
                dir = saveDir

        fileName = QFileDialog.getOpenFileName( self.gui.window,
            "Choose task file", dir, "Golem Task (*.gt)")
        if os.path.exists( fileName ):
            self._loadTask( fileName )

   ############################
    def _loadTask( self, filePath ):
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
            self._showNewTaskDialog( definition )

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

    ##########################
    def _contexMenuRequested( self, p ):
        self.__showTaskContextMenu( p )

    #############################
    def _taskTableRowClicked( self, row, col ):
        if row < self.gui.ui.taskTableWidget.rowCount():
            taskId = self.gui.ui.taskTableWidget.item( row, 0 ).text()
            taskId = "{}".format( taskId )
            t = self.logic.getTask( taskId )
            self.updateTaskAdditionalInfo( t )

    #############################
    def _taskTableRowDoubleClicked( self, m ):
        row = m.row()
        taskId = "{}".format( self.gui.ui.taskTableWidget.item( row, 0 ).text() )
        self.showDetailsDialog(taskId)

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
    def showChangeTaskDialog(self, taskId ):
        self.changeTaskDialog = ChangeTaskDialog( self.gui.window )
        self.changeTaskDialogCustomizer = ChangeTaskDialogCustomizer( self.changeTaskDialog, self.logic )
        ts = self.logic.getTask( taskId )
        self.changeTaskDialogCustomizer.loadTaskDefinition( ts.definition )
        self.changeTaskDialog.show()

    #############################
    def _showStatusClicked( self ):
        self.statusWindow = StatusWindow( self.gui.window )

        self.statusWindowCustomizer = StatusWindowCustomizer( self.statusWindow, self.logic )
        self.statusWindowCustomizer.getStatus()
        self.statusWindow.show()

    #############################
    def _showAboutClicked( self ):
        aboutWindow = AboutWindow( self.gui.window )
        aboutWindowCustomizer = AboutWindowCustomizer( aboutWindow, self.logic )
        aboutWindow.show()

     #############################
    def _showConfigurationDialogClicked( self ):
        self.configurationDialog = ConfigurationDialog( self.gui.window )
        self.configurationDialogCustomizer = ConfigurationDialogCustomizer( self.configurationDialog, self.logic )
        self.configurationDialogCustomizer.loadConfig()
        self.configurationDialog.show()

    #############################
    def _showEnvironments ( self ):
        self.environmentsDialog = EnvironmentsDialog( self.gui.window )

        self.environmentsDialogCustomizer = EnvironmentsDialogCustomizer( self.environmentsDialog, self.logic )
        self.environmentsDialog.show()
