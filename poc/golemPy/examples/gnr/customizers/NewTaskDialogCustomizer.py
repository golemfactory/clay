import os
from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog
from copy import deepcopy

from examples.gnr.ui.AddTaskResourcesDialog import AddTaskResourcesDialog

from examples.gnr.customizers.AddResourcesDialogCustomizer import AddResourcesDialogCustomizer
from examples.gnr.RenderingTaskState import RenderingTaskState
from examples.gnr.GNRTaskState import GNRTaskDefinition
from golem.task.TaskState import TaskStatus
from examples.gnr.customizers.TimeHelper import setTimeSpinBoxes, getTimeValues

import logging

logger = logging.getLogger(__name__)

class NewTaskDialogCustomizer:
    #############################
    def __init__( self, gui, logic ):

        self.gui    = gui
        self.logic  = logic
        self.options = None

        self.addTaskResourceDialog      = None
        self.taskState                  = None
        self.addTaskResourcesDialogCustomizer = None

        self._setupConnections()
        self._setUid()
        self._init()

    #############################
    def _setupConnections( self ):
        self._setupTaskTypeConnections()
        self._setupBasicNewTaskConnections()
        self._setupAdvanceNewTaskConnections()
        self._setupOptionsConnections()

    def _setupTaskTypeConnections( self ):
        QtCore.QObject.connect( self.gui.ui.taskTypeComboBox, QtCore.SIGNAL( "currentIndexChanged( const QString)" ), self._taskTypeValueChanged )

    #############################
    def _setupBasicNewTaskConnections( self ):
        self.gui.ui.saveButton.clicked.connect( self._saveTaskButtonClicked )
        self.gui.ui.chooseMainProgramFileButton.clicked.connect( self._chooseMainProgramFileButtonClicked )
        self.gui.ui.addResourceButton.clicked.connect( self._showAddResourcesDialog )
        self.gui.ui.finishButton.clicked.connect( self._finishButtonClicked )
        self.gui.ui.cancelButton.clicked.connect( self._cancelButtonClicked )

    #############################
    def _setupAdvanceNewTaskConnections( self ):
        QtCore.QObject.connect( self.gui.ui.optimizeTotalCheckBox, QtCore.SIGNAL( "stateChanged( int ) "), self._optimizeTotalCheckBoxChanged )

    #############################
    def _setupOptionsConnections( self ):
        self.gui.ui.optionsButton.clicked.connect( self._openOptions )

    #############################
    def _setUid( self ):
        self.gui.ui.taskIdLabel.setText( self._generateNewTaskUID() )

    #############################
    def _init( self ):
        self._setUid()

        taskTypes = self.logic.getTaskTypes()
        for t in taskTypes.values():
            self.gui.ui.taskTypeComboBox.addItem( t.name )

    #############################
    def _chooseMainProgramFileButtonClicked( self ):

        dir = os.path.dirname( u"{}".format( self.gui.ui.mainProgramFileLineEdit.text() ) )

        fileName = u"{}".format( QFileDialog.getOpenFileName( self.gui.window,
            "Choose main program file", dir, "Python (*.py)") )

        if fileName != '':
            self.gui.ui.mainProgramFileLineEdit.setText( fileName )

    ############################
    def _showAddResourcesDialog( self ):
        if not self.addTaskResourceDialog:
            self.addTaskResourceDialog = AddTaskResourcesDialog( self.gui.window )
            self.addTaskResourcesDialogCustomizer = AddResourcesDialogCustomizer( self.addTaskResourceDialog, self.logic )

        self.addTaskResourceDialog.show()

    ############################
    def _saveTaskButtonClicked( self ):
        fileName = QFileDialog.getSaveFileName( self.gui.window,
            "Choose save file", "", "Golem Task (*.gt)")

        if fileName != '':
            self._saveTask( fileName )

    ############################
    def _saveTask( self, filePath ):
        definition = self._queryTaskDefinition()
        self.logic.saveTask( definition, filePath )

    ############################
    def loadTaskDefinition( self, taskDefinition ):
        assert isinstance( taskDefinition, GNRTaskDefinition )

        definition = deepcopy( taskDefinition )

        self.gui.ui.taskIdLabel.setText( self._generateNewTaskUID() )
        self._loadBasicTaskParams( definition )
        self._loadAdvanceTaskParams( definition )
        self._loadResources( definition )

    #############################
    def setOptions( self, options ):
        self.options = options

    #############################
    def _loadResources( self, definition ):
        self.addTaskResourceDialog = AddTaskResourcesDialog( self.gui.window )
        self.addTaskResourcesDialogCustomizer = AddResourcesDialogCustomizer( self.addTaskResourceDialog, self.logic )
        self.addTaskResourcesDialogCustomizer.resources = definition.resources

        model = self.addTaskResourcesDialogCustomizer.gui.ui.folderTreeView.model()

        commonPrefix = os.path.commonprefix(definition.resources)
        self.addTaskResourcesDialogCustomizer.gui.ui.folderTreeView.setExpanded(model.index(commonPrefix), True)

        for res in definition.resources:
            pathHead, pathTail = os.path.split(res)
            while pathHead != '' and pathTail != '':
                self.addTaskResourcesDialogCustomizer.gui.ui.folderTreeView.setExpanded(model.index(pathHead), True)
                pathHead, pathTail = os.path.split(pathHead)

        # TODO
        self.addTaskResourcesDialogCustomizer.gui.ui.folderTreeView.model().addStartFiles(definition.resources)
        # for res in definition.resources:
        #     model.setData( model.index( res ), QtCore.Qt.Checked, QtCore.Qt.CheckStateRole )

    #############################
    def _loadBasicTaskParams( self, definition ):
        setTimeSpinBoxes( self.gui, definition.fullTaskTimeout, definition.subtaskTimeout, definition.minSubtaskTime )
        self.gui.ui.mainProgramFileLineEdit.setText( definition.mainProgramFile )
        self.gui.ui.totalSpinBox.setValue( definition.totalSubtasks )

        if os.path.normpath( definition.mainProgramFile ) in definition.resources:
            definition.resources.remove( os.path.normpath( definition.mainProgramFile ) )

        self._loadTaskType( definition )
        self._loadOptions( definition )


    ############################
    def _loadOptions( self, definition ):
        self.options = deepcopy( definition.options )

    ############################
    def _loadTaskType( self, definition ):
        try:
            taskTypeItem = self.gui.ui.taskTypeComboBox.findText( definition.taskType )
            if taskTypeItem >= 0:
                self.gui.ui.taskTypeComboBox.setCurrentIndex( taskTypeItem )
            else:
                logger.error( "Cannot load task, unknown task type" )
                return
        except Exception, err:
            logger.error("Wrong task type {}".format( str( err ) ) )
            return

    #############################
    def _loadAdvanceTaskParams( self, definition ):
        self.gui.ui.totalSpinBox.setEnabled( not definition.optimizeTotal )
        self.gui.ui.optimizeTotalCheckBox.setChecked( definition.optimizeTotal )

    #############################
    def _finishButtonClicked( self ):
        self.taskState = RenderingTaskState()
        self.taskState.status = TaskStatus.notStarted
        self.taskState.definition = self._queryTaskDefinition()
        self._addCurrentTask()

    #############################
    def _addCurrentTask( self ):
        self.logic.addTasks( [ self.taskState ] )
        self.gui.window.close()

    #############################
    def _cancelButtonClicked( self ):
        self.gui.window.close()

    #############################
    def _generateNewTaskUID( self ):
        import uuid
        return "{}".format( uuid.uuid4() )

    #############################
    def _queryTaskDefinition( self ):
        definition = GNRTaskDefinition()
        definition = self._readBasicTaskParams( definition )
        definition = self._readTaskType( definition )
        definition.options = self.options
        return definition

    #############################
    def _readBasicTaskParams( self, definition ):
        definition.taskId = u"{}".format( self.gui.ui.taskIdLabel.text() )
        definition.fullTaskTimeout, definition.subtaskTimeout, definition.minSubtaskTime = getTimeValues( self.gui )
        definition.mainProgramFile = u"{}".format( self.gui.ui.mainProgramFileLineEdit.text() )
        definition.optimizeTotal = self.gui.ui.optimizeTotalCheckBox.isChecked()
        if definition.optimizeTotal:
            definition.totalSubtasks = 0
        else:
            definition.totalSubtasks = self.gui.ui.totalSpinBox.value()

        definition.resources = self.addTaskResourcesDialogCustomizer.resources

        definition.resources.add( os.path.normpath( definition.mainProgramFile ) )

        return definition

    #############################
    def _readTaskType( self, definition ):
        definition.taskType = u"{}".format( self.gui.ui.taskTypeComboBox.currentText() )
        return definition

    #############################
    def _optimizeTotalCheckBoxChanged( self ):
        self.gui.ui.totalSpinBox.setEnabled( not self.gui.ui.optimizeTotalCheckBox.isChecked() )

    #############################
    def _openOptions( self ):
        taskName =  u"{}".format( self.gui.ui.taskTypeComboBox.currentText() )
        task = self.logic.getTaskType( taskName )
        dialog = task.dialog
        dialogCustomizer = task.dialogCustomizer
        if dialog is not None and dialogCustomizer is not None:
            taskDialog = dialog ( self.gui.window )
            taskDialogCustomizer = dialogCustomizer( taskDialog, self.logic, self )
            taskDialog.show()
        else:
            self.gui.ui.optionsButton.setEnabled( False )

    def _taskTypeValueChanged( self, name ):
        taskName =  u"{}".format( self.gui.ui.taskTypeComboBox.currentText() )
        task = self.logic.getTaskType( taskName )
        self.gui.ui.optionsButton.setEnabled( task.dialog is not None and task.dialogCustomizer is not None )
        self.options = deepcopy( task.options )
