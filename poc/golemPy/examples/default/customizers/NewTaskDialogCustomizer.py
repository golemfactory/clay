import os
from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog
from copy import deepcopy

from examples.default.ui.NewTaskDialog import NewTaskDialog
from examples.gnr.ui.AddTaskResourcesDialog import AddTaskResourcesDialog

from examples.gnr.customizers.AddResourcesDialogCustomizer import AddResourcesDialogCustomizer
from examples.gnr.TaskState import RenderingTaskState, RenderingTaskDefinition, GNRTaskDefinition
from golem.task.TaskState import TaskStatus
from examples.gnr.customizers.TimeHelper import setTimeSpinBoxes, getTimeValues
from examples.default.TaskType import buildPythonGNRTaskType

import logging

logger = logging.getLogger(__name__)

class NewTaskDialogCustomizer:
    #############################
    def __init__( self, gui, logic ):

        assert isinstance( gui, NewTaskDialog )

        self.gui    = gui
        self.logic  = logic

        self.__setupConnections()

        self.__init()

        self.addTaskResourceDialog      = None
        self.taskState                  = None
        self.addTaskResourcesDialogCustomizer = None

    #############################
    def __setupConnections( self ):
        self.gui.ui.saveButton.clicked.connect( self.__saveTaskButtonClicked )
        self.gui.ui.chooseMainProgramFileButton.clicked.connect( self.__choosMainProgramFileButtonClicked )
        self.gui.ui.addResourceButton.clicked.connect( self.__showAddResourcesDialog )
        self.gui.ui.finishButton.clicked.connect( self.__finishButtonClicked )
        self.gui.ui.cancelButton.clicked.connect( self.__cancelButtonClicked )

        QtCore.QObject.connect( self.gui.ui.optimizeTotalCheckBox, QtCore.SIGNAL( "stateChanged( int ) "), self.__optimizeTotalCheckBoxChanged )

    #############################
    def __init( self ):
        taskTypes = self.logic.getTaskTypes()

        self.gui.ui.taskIdLabel.setText( self.__generateNewTaskUID() )

        for t in taskTypes.values():
            self.gui.ui.taskTypeComboBox.addItem( t.name )

    #############################
    def __choosMainProgramFileButtonClicked( self ):

        dir = os.path.dirname( u"{}".format( self.gui.ui.mainProgramFileLineEdit.text() ) )

        fileName = u"{}".format( QFileDialog.getOpenFileName( self.gui.window,
            "Choose main program file", dir, "Python (*.py)") )

        if fileName != '':
            self.gui.ui.mainProgramFileLineEdit.setText( fileName )

    ############################
    def __showAddResourcesDialog( self ):
        if not self.addTaskResourceDialog:
            self.addTaskResourceDialog = AddTaskResourcesDialog( self.gui.window )
            self.addTaskResourcesDialogCustomizer = AddResourcesDialogCustomizer( self.addTaskResourceDialog, self.logic )

        self.addTaskResourceDialog.show()

    ############################
    def __saveTaskButtonClicked( self ):
        fileName = QFileDialog.getSaveFileName( self.gui.window,
            "Choose save file", "", "Golem Task (*.gt)")

        if fileName != '':
            self.__saveTask( fileName )

    ############################
    def __saveTask( self, filePath ):
        definition = self.__queryTaskDefinition()

        self.logic.saveTask( definition, filePath )

    ############################
    def loadTaskDefinition( self, taskDefinition ):
        assert isinstance( taskDefinition, GNRTaskDefinition )

        definition = deepcopy( taskDefinition )

        time            = QtCore.QTime()
        self.gui.ui.taskIdLabel.setText( self.__generateNewTaskUID() )

        setTimeSpinBoxes( self.gui, definition.fullTaskTimeout, definition.subtaskTimeout, definition.minSubtaskTime )

        self.gui.ui.mainProgramFileLineEdit.setText( definition.mainProgramFile )

        self.gui.ui.totalSpinBox.setRange( r.defaults.minSubtasks, r.defaults.maxSubtasks )
        self.gui.ui.totalSpinBox.setValue( definition.totalSubtasks )
        self.gui.ui.totalSpinBox.setEnabled( not definition.optimizeTotal )
        self.gui.ui.optimizeTotalCheckBox.setChecked( definition.optimizeTotal )

        if os.path.normpath( definition.mainProgramFile ) in definition.resources:
            definition.resources.remove( os.path.normpath( definition.mainProgramFile ) )

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
    def __finishButtonClicked( self ):
        self.taskState = RenderingTaskState()
        self.taskState.status = TaskStatus.notStarted
        self.taskState.definition = self.__queryTaskDefinition()
        self.taskState.definition.taskType = buildPythonGNRTaskType()
        self.logic.addTasks( [ self.taskState ] )
        self.gui.window.close()

    #############################
    def __cancelButtonClicked( self ):
        self.gui.window.close()

    #############################
    def __generateNewTaskUID( self ):
        import uuid
        return "{}".format( uuid.uuid4() )

    #############################
    def __getCurrentRenderer( self ):
        index = self.gui.ui.rendererComboBox.currentIndex()
        rendererName = self.gui.ui.rendererComboBox.itemText( index )
        return self.logic.getRenderer( u"{}".format( rendererName ) )

    #############################
    def __queryTaskDefinition( self ):
        definition      = GNRTaskDefinition()

        definition.taskId                = u"{}".format( self.gui.ui.taskIdLabel.text() )
        definition.fullTaskTimeout, definition.subtaskTimeout, definition.minSubtaskTime = getTimeValues( self.gui )
        definition.mainProgramFile   = u"{}".format( self.gui.ui.mainProgramFileLineEdit.text() )
        definition.optimizeTotal     = self.gui.ui.optimizeTotalCheckBox.isChecked()
        if definition.optimizeTotal:
            definition.totalSubtasks = 0
        else:
            definition.totalSubtasks = self.gui.ui.totalSpinBox.value()

        if self.addTaskResourcesDialogCustomizer:
            definition.resources         = self.rendererOptions.addToResources( self.addTaskResourcesDialogCustomizer.resources )

        definition.resources.add( os.path.normpath( definition.mainProgramFile ) )

        return definition

    def __optimizeTotalCheckBoxChanged( self ):
        self.gui.ui.totalSpinBox.setEnabled( not self.gui.ui.optimizeTotalCheckBox.isChecked() )