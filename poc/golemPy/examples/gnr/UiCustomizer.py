from PyQt4 import QtCore

from MainWindow import GNRMainWindow

from TaskTableElem import TaskTableElem

class UiCustomizer:
    ####################
    def __init__( self, gui, logic ):

        assert isinstance( gui, GNRMainWindow )

        self.gui    = gui
        self.logic  = logic
        QtCore.QObject.connect( self.gui, QtCore.SIGNAL( "taskTableRowClicked(int)" ), self.__taskTableRowClicked )
        QtCore.QObject.connect( self.gui, QtCore.SIGNAL( "showNewTaskDialogClicked()" ), self.__showNewTaskDialogClicked )

    ####################
    # Add new task to golem client
    def enqueueNewTask( self, uiNewTaskInfo ):
        self.logic.enqueueNewTask( uiNewTaskInfo )

    ####################
    # Updates tasks information in gui
    def updateTasks( self, tasks ):
        for i in range( self.gui.ui.renderTaskTableWidget.rowCount() ):
            taskID = self.gui.ui.renderTaskTableWidget.item( i, 0 ).text()
            taskID = "{}".format( taskID )
            if taskID in tasks:
                self.gui.ui.renderTaskTableWidget.item( i, 1 ).setText( tasks[ taskID ].status )
                progressBarInBoxLayout = self.gui.ui.renderTaskTableWidget.cellWidget( i, 2 )
                layout = progressBarInBoxLayout.layout()
                pb = layout.itemAt( 0 ).widget()
                pb.setProperty( "value", int( tasks[ taskID ].progress * 100.0 ) )
            else:
                assert False, "Trying to update not added task."
        
    ####################
    # Add task information in gui
    def addTask( self, task ):
        self.__addTask( task.id, task.status )

    ####################
    def updateTaskAdditionalInfo( self, id ):
        t = self.logic.getTask( id )
        from TaskStatus import TaskStatus
        assert isinstance( t, TaskStatus )

        self.gui.ui.minNodePower.setText( "{} ray per pixel".format( t.minPower ) )
        self.gui.ui.minSubtask.setText( "{} pixels".format( t.minSubtask ) )
        self.gui.ui.maxSubtask.setText( "{} pixels".format( t.maxSubtask ) )
        self.gui.ui.subtaskTimeout.setText( "{} minutes".format( int( t.subtaskTimeout / 60.0 ) ) )
        self.gui.ui.resolution.setText( "{} x {}".format( t.resolution[ 0 ], t.resolution[ 1 ] ) )
        self.gui.ui.renderer.setText( "{}".format( t.renderer ) )
        self.gui.ui.algorithmType.setText( "{}".format( t.algorithmType ) )
        self.gui.ui.pixelFilter.setText( "{}".format( t.pixelFilter ) )
        self.gui.ui.samplesPerPixel.setText( "{}".format( t.samplesPerPixelCount ) )
        self.gui.ui.outputFile.setText( "{}".format( t.outputFile ) )
        self.gui.ui.fullTaskTimeout.setText( "{}".format( t.fullTaskTimeout ) )
        self.gui.ui.timeStarted.setText( "{}".format( t.timeStarted ) )

    ############################
    def __addTask( self, id, status ):
        currentRowCount = self.gui.ui.renderTaskTableWidget.rowCount()
        self.gui.ui.renderTaskTableWidget.insertRow( currentRowCount )

        taskTableElem = TaskTableElem( id, status )

        for col in range( 0, 2 ): self.gui.ui.renderTaskTableWidget.setItem( currentRowCount, col, taskTableElem.getColumnItem( col ) )

        self.gui.ui.renderTaskTableWidget.setCellWidget( currentRowCount, 2, taskTableElem.progressBarInBoxLayoutWidget )

        self.updateTaskAdditionalInfo( id )


    def __updateRendererOptions( self, name ):
        r = self.logic.getRenderer( name )

        self.gui.newTaskDialog.ui.pixelFilterComboBox.clear()
        self.gui.newTaskDialog.ui.pixelFilterComboBox.addItems( r.filters )

        self.gui.newTaskDialog.ui.pathTracerComboBox.clear()
        self.gui.newTaskDialog.ui.pathTracerComboBox.addItems( r.pathTracers )

        self.gui.newTaskDialog.ui.outputFormatsComboBox.clear()
        self.gui.newTaskDialog.ui.outputFormatsComboBox.addItems( r.outputFormats )


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

        if self.gui.newTaskDialog:
            QtCore.QObject.connect( self.gui.newTaskDialog.ui.rendereComboBox, QtCore.SIGNAL( "currentIndexChanged( const QString )" ), self.__rendererComboBoxValueChanged )
        

            self.gui.newTaskDialog.ui.taskIdLabel.setText( self.__generateNewTaskUID() )

            for k in renderers:
                r = renderers[ k ]
                self.gui.newTaskDialog.ui.rendereComboBox.addItem( r.name )

            testTasks = self.logic.getTestTasks()
            for k in testTasks:
                tt = testTasks[ k ]
                self.gui.newTaskDialog.ui.testTaskComboBox.addItem( tt.name )

    #############################
    def __rendererComboBoxValueChanged( self, name ):
        self.__updateRendererOptions( "{}".format( name ) )

    #############################
    def __generateNewTaskUID( self ):
        import uuid
        return "{}".format( uuid.uuid1() )




