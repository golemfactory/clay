import os
from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog

from ui.NewTaskDialog import NewTaskDialog
from ui.AddTaskResourcesDialog import AddTaskResourcesDialog

from AddResourcesDialogCustomizer import AddResourcesDialogCustomizer
from TaskState import TaskState, TaskStatus


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
        self.gui.ui.chooseMainProgramFileButton.clicked.connect( self.__choosMainProgramFileButtonClicked )
        self.gui.ui.addResourceButton.clicked.connect( self.__showAddResourcesDialog )
        self.gui.ui.testTaskButton.clicked.connect( self.__testTaskButtonClicked )
        self.gui.ui.finishBatton.clicked.connect( self.__finishButtonClicked )
        self.gui.ui.cancelBatton.clicked.connect( self.__cancelButtonClicked )
        self.gui.ui.resetToDefaultButton.clicked.connect( self.__resetToDefaultButtonClicked )

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
            self.addTaskResourceDialog.ui.folderTreeView.model().checks = {}

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

    #############################
    def __chooseOutputFileButtonClicked( self ):

        cr = self.logic.getCurrentRenderer()

        outputFileType = "{}".format( self.gui.ui.outputFormatsComboBox.currentText() )
        filter = "{} (*.{})".format( outputFileType, outputFileType )

        dir = os.path.dirname( "{}".format( self.gui.ui.outputFileLineEdit.text() )  )

        fileName = "{}".format( QFileDialog.getSaveFileName( self.gui.window,
            "Choose output file", dir, filter ) )

        self.gui.ui.outputFileLineEdit.setText( fileName )

    #############################
    def __choosMainProgramFileButtonClicked( self ):

        dir = os.path.dirname( "{}".format( self.gui.ui.mainProgramFileLineEdit.text() )  )

        fileName = QFileDialog.getOpenFileName( self.gui.window,
            "Choose main program file", dir, "Python (*.py)")

        self.gui.ui.outputFileLineEdit.setText( fileName )

    ############################
    def __showAddResourcesDialog( self ):
        if not self.addTaskResourceDialog:
            self.addTaskResourceDialog = AddTaskResourcesDialog( self.gui.window )
            self.addTaskResourcesDialogCustomizer = AddResourcesDialogCustomizer( self.addTaskResourceDialog, self.logic )

        self.addTaskResourceDialog.show()

    ############################
    def __testTaskButtonClicked( self ):
        self.taskState = self.__queryTaskState()
        
        if self.logic.runTestTask( self.taskState ):
            self.gui.ui.finishBatton.setEnabled( True )
            self.gui.ui.testTaskButton.setEnabled( False )
        else:
            print "Task not tested properly"

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
    def __queryTaskState( self ):
        time    = QtCore.QTime()
        ts      = TaskState()

        ts.definition.algorithmType     = "{}".format( self.gui.ui.pathTracerComboBox.itemText( self.gui.ui.pathTracerComboBox.currentIndex() ) )     
        ts.definition.fullTaskTimeout   = time.secsTo( self.gui.ui.fullTaskTimeoutTimeEdit.time() )
        ts.definition.id                = "{}".format( self.gui.ui.taskIdLabel.text() )
        ts.definition.subtaskTimeout    = time.secsTo( self.gui.ui.subtaskTimeoutTimeEdit.time() )
        ts.definition.minSubtaskTime    = time.secsTo( self.gui.ui.minSubtaskTimeTimeEdit.time() )
        ts.definition.renderer          = self.logic.getRenderer( "{}".format( self.gui.ui.rendereComboBox.itemText( self.gui.ui.rendereComboBox.currentIndex() ) ) ).name
        ts.definition.pixelFilter       = "{}".format( self.gui.ui.pixelFilterComboBox.itemText( self.gui.ui.pixelFilterComboBox.currentIndex() ) )
        ts.definition.samplesPerPixelCount = self.gui.ui.samplesPerPixelSpinBox.value()
        ts.definition.resolution        = [ self.gui.ui.outputResXSpinBox.value(), self.gui.ui.outputResYSpinBox.value() ]
        ts.definition.outputFile        = "{}".format( self.gui.ui.outputFileLineEdit.text() )
        ts.definition.mainProgramFile   = "{}".format( self.gui.ui.mainProgramFileLineEdit.text() )
        ts.definition.outputFormat      = "{}".format( self.gui.ui.outputFormatsComboBox.itemText( self.gui.ui.outputFormatsComboBox.currentIndex() ) )
        ts.status                       = TaskStatus.notStarted

        if self.addTaskResourcesDialogCustomizer:
            ts.definition.resources         = self.addTaskResourcesDialogCustomizer.resources
            ts.definition.mainSceneFile     = "{}".format( self.addTaskResourcesDialogCustomizer.gui.ui.mainSceneLabel.text() )

        

        return ts





