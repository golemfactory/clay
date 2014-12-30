import os
from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog
from copy import deepcopy

from examples.gnr.ui.NewTaskDialog import NewTaskDialog
from examples.gnr.ui.AddTaskResourcesDialog import AddTaskResourcesDialog

from AddResourcesDialogCustomizer import AddResourcesDialogCustomizer
from examples.gnr.TaskState import GNRTaskState, TaskDefinition, AdvanceVerificationOption
from golem.task.TaskState import TaskStatus
from TimeHelper import setTimeSpinBoxes, getTimeValues

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
        QtCore.QObject.connect( self.gui.ui.rendererComboBox, QtCore.SIGNAL( "currentIndexChanged( const QString )" ), self.__rendererComboBoxValueChanged )
        self.gui.ui.chooseOutputFileButton.clicked.connect( self.__chooseOutputFileButtonClicked )
        self.gui.ui.saveButton.clicked.connect( self.__saveTaskButtonClicked )
        self.gui.ui.chooseMainProgramFileButton.clicked.connect( self.__choosMainProgramFileButtonClicked )
        self.gui.ui.addResourceButton.clicked.connect( self.__showAddResourcesDialog )
        self.gui.ui.testTaskButton.clicked.connect( self.__testTaskButtonClicked )
        self.gui.ui.finishButton.clicked.connect( self.__finishButtonClicked )
        self.gui.ui.cancelButton.clicked.connect( self.__cancelButtonClicked )
        self.gui.ui.resetToDefaultButton.clicked.connect( self.__resetToDefaultButtonClicked )
        self.gui.ui.rendererOptionsButton.clicked.connect( self.__openRendererOptions )

        QtCore.QObject.connect(self.gui.ui.outputResXSpinBox, QtCore.SIGNAL("valueChanged( const QString )"), self.__resXChanged)
        QtCore.QObject.connect(self.gui.ui.outputResYSpinBox, QtCore.SIGNAL("valueChanged( const QString )"), self.__resYChanged)

        QtCore.QObject.connect( self.gui.ui.optimizeTotalCheckBox, QtCore.SIGNAL( "stateChanged( int ) "), self.__optimizeTotalCheckBoxChanged )
        QtCore.QObject.connect(self.gui.ui.advanceVerificationCheckBox, QtCore.SIGNAL( "stateChanged( int )" ), self.__advanceVerificationChanged )
        QtCore.QObject.connect(self.gui.ui.fullTaskTimeoutHourSpinBox, QtCore.SIGNAL("valueChanged( const QString )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.fullTaskTimeoutMinSpinBox, QtCore.SIGNAL("valueChanged( const QString )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.fullTaskTimeoutSecSpinBox, QtCore.SIGNAL("valueChanged( const QString )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.minSubtaskTimeHourSpinBox, QtCore.SIGNAL("valueChanged( const QString )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.minSubtaskTimeMinSpinBox, QtCore.SIGNAL("valueChanged( const QString )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.minSubtaskTimeSecSpinBox, QtCore.SIGNAL("valueChanged( const QString )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.subtaskTimeoutHourSpinBox, QtCore.SIGNAL("valueChanged( const QString )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.subtaskTimeoutMinSpinBox, QtCore.SIGNAL("valueChanged( const QString )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.subtaskTimeoutSecSpinBox, QtCore.SIGNAL("valueChanged( const QString )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.mainProgramFileLineEdit, QtCore.SIGNAL("textChanged( const QString )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.outputFormatsComboBox, QtCore.SIGNAL("currentIndexChanged( const QString )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.outputFileLineEdit, QtCore.SIGNAL("textChanged( const QString )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.totalSpinBox, QtCore.SIGNAL( "valueChanged( const QString )" ), self.__taskSettingsChanged )
        QtCore.QObject.connect(self.gui.ui.verificationSizeXSpinBox, QtCore.SIGNAL( "valueChanged( const QString )" ), self.__taskSettingsChanged )
        QtCore.QObject.connect(self.gui.ui.verificationSizeYSpinBox, QtCore.SIGNAL( "valueChanged( const QString )" ), self.__taskSettingsChanged )
        QtCore.QObject.connect(self.gui.ui.verificationForAllRadioButton, QtCore.SIGNAL( "toggled( bool )" ), self.__taskSettingsChanged )

    #############################
    def __init( self ):
        renderers = self.logic.getRenderers()
        dr = self.logic.getDefaultRenderer()
        self.rendererOptions = dr.options()

        self.gui.ui.taskIdLabel.setText( self.__generateNewTaskUID() )

        for k in renderers:
            r = renderers[ k ]
            self.gui.ui.rendererComboBox.addItem( r.name )

        self.gui.ui.totalSpinBox.setRange( dr.defaults.minSubtasks, dr.defaults.maxSubtasks )
        self.gui.ui.totalSpinBox.setValue( dr.defaults.defaultSubtasks )

        self.gui.ui.outputResXSpinBox.setValue ( dr.defaults.resolution[0] )
        self.gui.ui.outputResYSpinBox.setValue ( dr.defaults.resolution[1] )
        self.gui.ui.verificationSizeXSpinBox.setMaximum( dr.defaults.resolution[0] )
        self.gui.ui.verificationSizeYSpinBox.setMaximum( dr.defaults.resolution[1] )

    #############################
    def __updateRendererOptions( self, name ):
        r = self.logic.getRenderer( name )

        if r:
            self.logic.setCurrentRenderer( name )
            self.rendererOptions = r.options()

            self.gui.ui.outputFormatsComboBox.clear()
            self.gui.ui.outputFormatsComboBox.addItems( r.outputFormats )

            for i in range( len( r.outputFormats ) ):
                if r.outputFormats[ i ] == r.defaults.outputFormat:
                    self.gui.ui.outputFormatsComboBox.setCurrentIndex( i )

            self.gui.ui.mainProgramFileLineEdit.setText( r.defaults.mainProgramFile )

            setTimeSpinBoxes( self.gui, r.defaults.fullTaskTimeout, r.defaults.subtaskTimeout, r.defaults.minSubtaskTime )

            self.gui.ui.totalSpinBox.setRange( r.defaults.minSubtasks, r.defaults.maxSubtasks )

        else:
            assert False, "Unreachable"

    #############################
    def __resetToDefaults( self ):
        dr = self.__getCurrentRenderer()


        self.rendererOptions = dr.options()
        self.logic.setCurrentRenderer( dr.name )

        self.gui.ui.outputFormatsComboBox.clear()
        self.gui.ui.outputFormatsComboBox.addItems( dr.outputFormats )

        for i in range( len( dr.outputFormats ) ):
            if dr.outputFormats[ i ] == dr.defaults.outputFormat:
                self.gui.ui.outputFormatsComboBox.setCurrentIndex( i )

        self.gui.ui.mainProgramFileLineEdit.setText( dr.defaults.mainProgramFile )

        setTimeSpinBoxes( self.gui, dr.defaults.fullTaskTimeout, dr.defaults.subtaskTimeout, dr.defaults.minSubtaskTime )

        self.gui.ui.outputFileLineEdit.clear()

        self.gui.ui.outputResXSpinBox.setValue( dr.defaults.resolution[0] )
        self.gui.ui.outputResYSpinBox.setValue( dr.defaults.resolution[1] )

        if self.addTaskResourceDialog:
            self.addTaskResourcesDialogCustomizer.resources = set()
            self.addTaskResourcesDialogCustomizer.gui.ui.mainSceneLabel.clear()
            self.addTaskResourceDialog.ui.folderTreeView.model().addStartFiles([])
            self.addTaskResourceDialog.ui.folderTreeView.model().checks = {}

        self.gui.ui.finishButton.setEnabled( False )
        self.gui.ui.testTaskButton.setEnabled( True )

        self.gui.ui.totalSpinBox.setRange( dr.defaults.minSubtasks, dr.defaults.maxSubtasks )
        self.gui.ui.totalSpinBox.setValue( dr.defaults.defaultSubtasks )
        self.gui.ui.totalSpinBox.setEnabled( True )
        self.gui.ui.optimizeTotalCheckBox.setChecked( False )

    # SLOTS
    #############################
    def __taskTableRowClicked( self, row ):
        if row < self.gui.ui.renderTaskTableWidget.rowCount():
            taskId = self.gui.ui.renderTaskTableWidget.item( row, 0 ).text()
            taskId = "{}".format( taskId )
            self.updateTaskAdditionalInfo( taskId )

    #############################
    def __showNewTaskDialogClicked( self ):
        renderers = self.logic.getRenderers()
            
        self.__setupNewTaskDialogConnections( self.gui.ui )

        self.gui.ui.taskIdLabel.setText( self.__generateNewTaskUID() )

        for k in renderers:
            r = renderers[ k ]
            self.gui.ui.rendererComboBox.addItem( r.name )

    #############################
    def __rendererComboBoxValueChanged( self, name ):
        self.__updateRendererOptions( "{}".format( name ) )

    #############################
    def __taskSettingsChanged( self, name = None ):
        self.gui.ui.finishButton.setEnabled( False )
        self.gui.ui.testTaskButton.setEnabled( True )

    #############################
    def __chooseOutputFileButtonClicked( self ):

        cr = self.logic.getCurrentRenderer()

        outputFileType = u"{}".format( self.gui.ui.outputFormatsComboBox.currentText() )
        filter = u"{} (*.{})".format( outputFileType, outputFileType )

        dir = os.path.dirname( u"{}".format( self.gui.ui.outputFileLineEdit.text() )  )

        fileName = u"{}".format( QFileDialog.getSaveFileName( self.gui.window,
            "Choose output file", dir, filter ) )

        if fileName != '':
            self.gui.ui.outputFileLineEdit.setText( fileName )
            self.gui.ui.finishButton.setEnabled( False )
            self.gui.ui.testTaskButton.setEnabled( True )

    #############################
    def __choosMainProgramFileButtonClicked( self ):

        dir = os.path.dirname( u"{}".format( self.gui.ui.mainProgramFileLineEdit.text() ) )

        fileName = u"{}".format( QFileDialog.getOpenFileName( self.gui.window,
            "Choose main program file", dir, "Python (*.py)") )

        if fileName != '':
            self.gui.ui.mainProgramFileLineEdit.setText( fileName )
            self.gui.ui.finishButton.setEnabled( False )
            self.gui.ui.testTaskButton.setEnabled( True )

    ############################
    def __showAddResourcesDialog( self ):
        if not self.addTaskResourceDialog:
            self.addTaskResourceDialog = AddTaskResourcesDialog( self.gui.window )
            self.addTaskResourcesDialogCustomizer = AddResourcesDialogCustomizer( self.addTaskResourceDialog, self.logic )

        self.addTaskResourceDialog.show()
        self.gui.ui.finishButton.setEnabled( False )
        self.gui.ui.testTaskButton.setEnabled( True )

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
        assert isinstance( taskDefinition, TaskDefinition )

        definition = deepcopy( taskDefinition )

        rendererItem = self.gui.ui.rendererComboBox.findText( definition.renderer )


        if rendererItem >= 0:
            self.gui.ui.rendererComboBox.setCurrentIndex( rendererItem )
        else:
            logger.error( "Cannot load task, wrong renderer" )
            return

        r = self.logic.getRenderer( definition.renderer )

        self.rendererOptions = deepcopy( definition.rendererOptions )

        time            = QtCore.QTime()
        self.gui.ui.taskIdLabel.setText( self.__generateNewTaskUID() )

        setTimeSpinBoxes( self.gui, definition.fullTaskTimeout, definition.subtaskTimeout, definition.minSubtaskTime )

        self.gui.ui.outputResXSpinBox.setValue( definition.resolution[ 0 ] )
        self.gui.ui.outputResYSpinBox.setValue( definition.resolution[ 1 ] )
        self.gui.ui.outputFileLineEdit.setText( definition.outputFile )

        self.gui.ui.mainProgramFileLineEdit.setText( definition.mainProgramFile )

        outputFormatItem = self.gui.ui.outputFormatsComboBox.findText( definition.outputFormat )

        if outputFormatItem >= 0:
            self.gui.ui.outputFormatsComboBox.setCurrentIndex( outputFormatItem )
        else:
            logger.error( "Cannot load task, wrong output format" )
            return

        self.gui.ui.totalSpinBox.setRange( r.defaults.minSubtasks, r.defaults.maxSubtasks )
        self.gui.ui.totalSpinBox.setValue( definition.totalSubtasks )
        self.gui.ui.totalSpinBox.setEnabled( not definition.optimizeTotal )
        self.gui.ui.optimizeTotalCheckBox.setChecked( definition.optimizeTotal )

        if os.path.normpath( definition.mainProgramFile ) in definition.resources:
            definition.resources.remove( os.path.normpath( definition.mainProgramFile ) )
        if os.path.normpath( definition.mainSceneFile ) in definition.resources:
            definition.resources.remove( os.path.normpath( definition.mainSceneFile ) )
        definition.resources = definition.rendererOptions.removeFromResources( definition.resources )

        self.addTaskResourceDialog = AddTaskResourcesDialog( self.gui.window )
        self.addTaskResourcesDialogCustomizer = AddResourcesDialogCustomizer( self.addTaskResourceDialog, self.logic )
        self.addTaskResourcesDialogCustomizer.resources = definition.resources
        self.addTaskResourcesDialogCustomizer.gui.ui.mainSceneLabel.setText( definition.mainSceneFile )

        model = self.addTaskResourcesDialogCustomizer.gui.ui.folderTreeView.model()

        commonPrefix = os.path.commonprefix(definition.resources)
        self.addTaskResourcesDialogCustomizer.gui.ui.folderTreeView.setExpanded(model.index(commonPrefix), True)

        for res in definition.resources:
            pathHead, pathTail = os.path.split(res)
            while pathHead != '' and pathTail != '':
                self.addTaskResourcesDialogCustomizer.gui.ui.folderTreeView.setExpanded(model.index(pathHead), True)
                pathHead, pathTail = os.path.split(pathHead)

        self.__loadVerificationParameters( definition )

        # TODO
        self.addTaskResourcesDialogCustomizer.gui.ui.folderTreeView.model().addStartFiles(definition.resources)
        # for res in definition.resources:
        #     model.setData( model.index( res ), QtCore.Qt.Checked, QtCore.Qt.CheckStateRole )

    ############################
    def __loadVerificationParameters( self, definition ):
        enabled = definition.verificationOptions is not None

        self.__setVerificationWidgetsState( enabled )
        if enabled:
            self.gui.ui.advanceVerificationCheckBox.setCheckState( QtCore.Qt.Checked )
            self.gui.ui.verificationSizeXSpinBox.setValue( definition.verificationOptions.boxSize[0])
            self.gui.ui.verificationSizeYSpinBox.setValue( definition.verificationOptions.boxSize[1])
            self.gui.ui.verificationForAllRadioButton.setChecked( definition.verificationOptions.forAll )
            self.gui.ui.verificationForFirstRadioButton.setChecked( not definition.verificationOptions.forAll )
        else:
            self.gui.ui.advanceVerificationCheckBox.setCheckState( QtCore.Qt.Unchecked )

    ############################
    def __setVerificationWidgetsState( self, state ):
        self.gui.ui.verificationForAllRadioButton.setEnabled( state )
        self.gui.ui.verificationForFirstRadioButton.setEnabled( state )
        self.gui.ui.verificationSizeXSpinBox.setEnabled( state )
        self.gui.ui.verificationSizeYSpinBox.setEnabled( state )

    ############################
    def __testTaskButtonClicked( self ):
        self.taskState = GNRTaskState()
        self.taskState.status = TaskStatus.notStarted
        self.taskState.definition = self.__queryTaskDefinition()
        
        if not self.logic.runTestTask( self.taskState ):
            logger.error( "Task not tested properly" )

    def testTaskComputationFinished( self, success, estMem ):
        if success:
            self.taskState.definition.estimatedMemory  = estMem
            self.gui.ui.finishButton.setEnabled( True )
            self.gui.ui.testTaskButton.setEnabled( False )

    #############################
    def __finishButtonClicked( self ):
        self.logic.addTasks( [ self.taskState ] )
        self.gui.window.close()

    #############################
    def __cancelButtonClicked( self ):
        self.__resetToDefaults()
        self.gui.window.close()

    def __resetToDefaultButtonClicked( self ):
        self.__resetToDefaults()

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
        definition      = TaskDefinition()

        definition.taskId                = u"{}".format( self.gui.ui.taskIdLabel.text() )
        definition.fullTaskTimeout, definition.subtaskTimeout, definition.minSubtaskTime = getTimeValues( self.gui )
        definition.renderer          = self.__getCurrentRenderer().name
        definition.rendererOptions   = deepcopy( self.rendererOptions )
        definition.resolution        = [ self.gui.ui.outputResXSpinBox.value(), self.gui.ui.outputResYSpinBox.value() ]
        definition.outputFile        = u"{}".format( self.gui.ui.outputFileLineEdit.text() )
        definition.mainProgramFile   = u"{}".format( self.gui.ui.mainProgramFileLineEdit.text() )
        definition.outputFormat      = u"{}".format( self.gui.ui.outputFormatsComboBox.itemText( self.gui.ui.outputFormatsComboBox.currentIndex() ) )
        definition.optimizeTotal     = self.gui.ui.optimizeTotalCheckBox.isChecked()
        if definition.optimizeTotal:
            definition.totalSubtasks = 0
        else:
            definition.totalSubtasks = self.gui.ui.totalSpinBox.value()

        if self.addTaskResourcesDialogCustomizer:
            definition.resources         = self.rendererOptions.addToResources( self.addTaskResourcesDialogCustomizer.resources )
            definition.mainSceneFile     = u"{}".format( self.addTaskResourcesDialogCustomizer.gui.ui.mainSceneLabel.text() )

            definition.resources.add( os.path.normpath( definition.mainSceneFile ) )

        definition.resources.add( os.path.normpath( definition.mainProgramFile ) )

        self.__queryAdvanceVerification( definition )

        return definition

    def __queryAdvanceVerification( self, definition ):
        if self.gui.ui.advanceVerificationCheckBox.isChecked():
            definition.verificationOptions = AdvanceVerificationOption()
            definition.verificationOptions.forAll = self.gui.ui.verificationForAllRadioButton.isChecked()
            definition.verificationOptions.boxSize = ( int( self.gui.ui.verificationSizeXSpinBox.value() ), int( self.gui.ui.verificationSizeYSpinBox.value() ) )
        else:
            definition.verificationOptions = None

    def __optimizeTotalCheckBoxChanged( self ):
        self.gui.ui.totalSpinBox.setEnabled( not self.gui.ui.optimizeTotalCheckBox.isChecked() )
        self.__taskSettingsChanged()

    #############################
    def __openRendererOptions( self ):
         rendererName = self.gui.ui.rendererComboBox.itemText( self.gui.ui.rendererComboBox.currentIndex() )
         renderer = self.logic.getRenderer( u"{}".format( rendererName ) )
         dialog = renderer.dialog
         dialogCustomizer = renderer.dialogCustomizer
         rendererDialog = dialog( self.gui.window )
         rendererDialogCustomizer = dialogCustomizer( rendererDialog, self.logic, self )
         rendererDialog.show()

    def setRendererOptions( self, options ):
        self.rendererOptions = options
        self.__taskSettingsChanged()

    def getRendererOptions( self ):
        return self.rendererOptions

    #############################
    def __advanceVerificationChanged( self ):
        state = self.gui.ui.advanceVerificationCheckBox.isChecked()
        self.__setVerificationWidgetsState( state )
        self.__taskSettingsChanged()

    #############################
    def __resXChanged( self ):
        self.gui.ui.verificationSizeXSpinBox.setMaximum( self.gui.ui.outputResXSpinBox.value() )
        self.__taskSettingsChanged()

    #############################
    def __resYChanged( self ):
        self.gui.ui.verificationSizeYSpinBox.setMaximum( self.gui.ui.outputResYSpinBox.value() )
        self.__taskSettingsChanged()