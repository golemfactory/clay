import os
from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog

from examples.gnr.ui.NewTaskDialog import NewTaskDialog
from examples.gnr.ui.AddTaskResourcesDialog import AddTaskResourcesDialog

from AddResourcesDialogCustomizer import AddResourcesDialogCustomizer
from examples.gnr.TaskState import GNRTaskState, TaskDefinition
from golem.task.TaskState import TaskStatus

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
        QtCore.QObject.connect( self.gui.ui.rendereComboBox, QtCore.SIGNAL( "currentIndexChanged( const QString )" ), self.__rendererComboBoxValueChanged )
        self.gui.ui.chooseOutputFileButton.clicked.connect( self.__chooseOutputFileButtonClicked )
        self.gui.ui.saveButton.clicked.connect( self.__saveTaskButtonClicked )
        self.gui.ui.chooseMainProgramFileButton.clicked.connect( self.__choosMainProgramFileButtonClicked )
        self.gui.ui.addResourceButton.clicked.connect( self.__showAddResourcesDialog )
        self.gui.ui.testTaskButton.clicked.connect( self.__testTaskButtonClicked )
        self.gui.ui.finishButton.clicked.connect( self.__finishButtonClicked )
        self.gui.ui.cancelButton.clicked.connect( self.__cancelButtonClicked )
        self.gui.ui.resetToDefaultButton.clicked.connect( self.__resetToDefaultButtonClicked )

        QtCore.QObject.connect(self.gui.ui.pixelFilterComboBox, QtCore.SIGNAL("currentIndexChanged( const QString )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.pathTracerComboBox, QtCore.SIGNAL("currentIndexChanged( const QString )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.samplesPerPixelSpinBox, QtCore.SIGNAL("valueChanged( const QString )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.fullTaskTimeoutTimeEdit, QtCore.SIGNAL("timeChanged( const QTime )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.minSubtaskTimeTimeEdit, QtCore.SIGNAL("timeChanged( const QTime )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.subtaskTimeoutTimeEdit, QtCore.SIGNAL("timeChanged( const QTime )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.testTaskComboBox, QtCore.SIGNAL("currentIndexChanged( const QString )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.mainProgramFileLineEdit, QtCore.SIGNAL("textChanged( const QString )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.outputFormatsComboBox, QtCore.SIGNAL("currentIndexChanged( const QString )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.outputResXSpinBox, QtCore.SIGNAL("valueChanged( const QString )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.outputResYSpinBox, QtCore.SIGNAL("valueChanged( const QString )"), self.__taskSettingsChanged)
        QtCore.QObject.connect(self.gui.ui.outputFileLineEdit, QtCore.SIGNAL("textChanged( const QString )"), self.__taskSettingsChanged)


    #############################
    def __updateRendererOptions( self, name ):
        r = self.logic.getRenderer( name )

        if r:
            self.logic.setCurrentRenderer( name )
            self.gui.ui.pixelFilterComboBox.clear()
            self.gui.ui.pixelFilterComboBox.addItems( r.filters )

            self.gui.ui.pathTracerComboBox.clear()
            self.gui.ui.pathTracerComboBox.addItems( r.pathTracers )

            self.gui.ui.outputFormatsComboBox.clear()
            self.gui.ui.outputFormatsComboBox.addItems( r.outputFormats )

            for i in range( len( r.outputFormats ) ):
                if r.outputFormats[ i ] == r.defaults.outputFormat:
                    self.gui.ui.outputFormatsComboBox.setCurrentIndex( i )

            self.gui.ui.mainProgramFileLineEdit.setText( r.defaults.mainProgramFile )

            time = QtCore.QTime()
            self.gui.ui.fullTaskTimeoutTimeEdit.setTime( time.addSecs( r.defaults.fullTaskTimeout ) )
            self.gui.ui.subtaskTimeoutTimeEdit.setTime( time.addSecs( r.defaults.subtaskTimeout ) )
            self.gui.ui.minSubtaskTimeTimeEdit.setTime( time.addSecs( r.defaults.minSubtaskTime ) )

            self.gui.ui.samplesPerPixelSpinBox.setValue( r.defaults.samplesPerPixel )

        else:
            assert False, "Unreachable"

    #############################
    def __resetToDefaults( self ):
        dr = self.logic.getDefaultRenderer()

        self.logic.setCurrentRenderer( dr.name )
        self.gui.ui.pixelFilterComboBox.clear()
        self.gui.ui.pixelFilterComboBox.addItems( dr.filters )

        self.gui.ui.pathTracerComboBox.clear()
        self.gui.ui.pathTracerComboBox.addItems( dr.pathTracers )

        self.gui.ui.outputFormatsComboBox.clear()
        self.gui.ui.outputFormatsComboBox.addItems( dr.outputFormats )

        for i in range( len( dr.outputFormats ) ):
            if dr.outputFormats[ i ] == dr.defaults.outputFormat:
                self.gui.ui.outputFormatsComboBox.setCurrentIndex( i )

        self.gui.ui.mainProgramFileLineEdit.setText( dr.defaults.mainProgramFile )

        time = QtCore.QTime()
        self.gui.ui.fullTaskTimeoutTimeEdit.setTime( time.addSecs( dr.defaults.fullTaskTimeout ) )
        self.gui.ui.subtaskTimeoutTimeEdit.setTime( time.addSecs( dr.defaults.subtaskTimeout ) )
        self.gui.ui.minSubtaskTimeTimeEdit.setTime( time.addSecs( dr.defaults.minSubtaskTime ) )

        self.gui.ui.outputFileLineEdit.clear()

        self.gui.ui.samplesPerPixelSpinBox.setValue( dr.defaults.samplesPerPixel )

        self.gui.ui.outputResXSpinBox.setValue( dr.defaults.outputResX )
        self.gui.ui.outputResYSpinBox.setValue( dr.defaults.outputResY )

        if self.addTaskResourceDialog:
            self.addTaskResourcesDialogCustomizer.resources = []
            self.addTaskResourcesDialogCustomizer.gui.ui.mainSceneLabel.clear()
            self.addTaskResourceDialog.ui.folderTreeView.model().addStartFiles([])
            self.addTaskResourceDialog.ui.folderTreeView.model().checks = {}

        self.gui.ui.finishButton.setEnabled( False )
        self.gui.ui.testTaskButton.setEnabled( True )

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
            self.gui.ui.rendereComboBox.addItem( r.name )

        testTasks = self.logic.getTestTasks()
        for k in testTasks:
            tt = testTasks[ k ]
            self.gui.ui.testTaskComboBox.addItem( tt.name )

    #############################
    def __rendererComboBoxValueChanged( self, name ):
        self.__updateRendererOptions( "{}".format( name ) )

    def __taskSettingsChanged( self, name ):
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
    def loadTaskDefinition( self, definition ):
        assert isinstance( definition, TaskDefinition )
        rendererItem = self.gui.ui.rendereComboBox.findText( definition.renderer )

        if rendererItem >= 0:
            self.gui.ui.rendereComboBox.setCurrentIndex( rendererItem )
        else:
            logger.error( "Cannot load task, wrong renderer" )
            return

        algItem = self.gui.ui.pathTracerComboBox.findText( definition.algorithmType )

        if algItem >= 0:
            self.gui.ui.pathTracerComboBox.setCurrentIndex( algItem )
        else:
            logger.error( "Cannot load task, wrong algorithm " )
            return

        time            = QtCore.QTime()
        self.gui.ui.taskIdLabel.setText( self.__generateNewTaskUID() )
        self.gui.ui.fullTaskTimeoutTimeEdit.setTime( time.addMSecs( definition.fullTaskTimeout ) )
        self.gui.ui.subtaskTimeoutTimeEdit.setTime( time.addMSecs( definition.subtaskTimeout ) )
        self.gui.ui.minSubtaskTimeTimeEdit.setTime( time.addMSecs( definition.minSubtaskTime ) )

        pixelFilterItem = self.gui.ui.pixelFilterComboBox.findText( definition.pixelFilter )

        if pixelFilterItem >= 0:
            self.gui.ui.pixelFilterComboBox.setCurrentIndex( pixelFilterItem )
        else:
            logger.error( "Cannot load task, wrong  pixel filter" )
            return

        self.gui.ui.samplesPerPixelSpinBox.setValue( definition.samplesPerPixelCount )
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

        # TODO
        self.addTaskResourcesDialogCustomizer.gui.ui.folderTreeView.model().addStartFiles(definition.resources)
        # for res in definition.resources:
        #     model.setData( model.index( res ), QtCore.Qt.Checked, QtCore.Qt.CheckStateRole )


    ############################
    def __testTaskButtonClicked( self ):
        self.taskState = GNRTaskState()
        self.taskState.status = TaskStatus.notStarted
        self.taskState.definition = self.__queryTaskDefinition()
        
        if not self.logic.runTestTask( self.taskState ):
            logger.error( "Task not tested properly" )

    def testTaskComputationFinished( self, success ):
        if success:
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
    def __init( self ):
        renderers = self.logic.getRenderers()

        self.gui.ui.taskIdLabel.setText( self.__generateNewTaskUID() )

        for k in renderers:
            r = renderers[ k ]
            self.gui.ui.rendereComboBox.addItem( r.name )

        testTasks = self.logic.getTestTasks()
        for k in testTasks:
            tt = testTasks[ k ]
            self.gui.ui.testTaskComboBox.addItem( tt.name )

    #############################
    def __queryTaskDefinition( self ):
        time            = QtCore.QTime()
        definition      = TaskDefinition()

        definition.algorithmType     = u"{}".format( self.gui.ui.pathTracerComboBox.itemText( self.gui.ui.pathTracerComboBox.currentIndex() ) )
        definition.fullTaskTimeout   = time.secsTo( self.gui.ui.fullTaskTimeoutTimeEdit.time() )
        definition.id                = u"{}".format( self.gui.ui.taskIdLabel.text() )
        definition.subtaskTimeout    = time.secsTo( self.gui.ui.subtaskTimeoutTimeEdit.time() )
        definition.minSubtaskTime    = time.secsTo( self.gui.ui.minSubtaskTimeTimeEdit.time() )
        definition.renderer          = self.logic.getRenderer( "{}".format( self.gui.ui.rendereComboBox.itemText( self.gui.ui.rendereComboBox.currentIndex() ) ) ).name
        definition.pixelFilter       = u"{}".format( self.gui.ui.pixelFilterComboBox.itemText( self.gui.ui.pixelFilterComboBox.currentIndex() ) )
        definition.samplesPerPixelCount = self.gui.ui.samplesPerPixelSpinBox.value()
        definition.resolution        = [ self.gui.ui.outputResXSpinBox.value(), self.gui.ui.outputResYSpinBox.value() ]
        definition.outputFile        = u"{}".format( self.gui.ui.outputFileLineEdit.text() )
        definition.mainProgramFile   = u"{}".format( self.gui.ui.mainProgramFileLineEdit.text() )
        definition.outputFormat      = u"{}".format( self.gui.ui.outputFormatsComboBox.itemText( self.gui.ui.outputFormatsComboBox.currentIndex() ) )

        if self.addTaskResourcesDialogCustomizer:
            definition.resources         = self.addTaskResourcesDialogCustomizer.resources
            definition.mainSceneFile     = u"{}".format( self.addTaskResourcesDialogCustomizer.gui.ui.mainSceneLabel.text() )

        

        return definition





