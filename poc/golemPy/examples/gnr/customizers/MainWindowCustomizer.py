import os
import datetime
from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog, QTreeWidgetItem

from MainWindow import GNRMainWindow
from NewTaskDialog import NewTaskDialog
from ShowTaskResourcesDialog import ShowTaskResourcesDialog
from NewTaskDialogCustomizer import NewTaskDialogCustomizer

from TaskTableElem import TaskTableElem


class MainWindowCustomizer:
    ############################
    def __init__( self, gui, logic ):

        assert isinstance( gui, GNRMainWindow )

        self.gui    = gui
        self.logic  = logic

        self.__setupConnections()
        self.currentTaskHighlighted = None

    #############################
    def __setupConnections( self ):
        QtCore.QObject.connect( self.gui.ui.actionNew, QtCore.SIGNAL( "triggered()" ), self.__showNewTaskDialogClicked )
        QtCore.QObject.connect( self.gui.ui.renderTaskTableWidget, QtCore.SIGNAL( "cellClicked(int, int)" ), self.__taskTableRowClicked )
        self.gui.ui.showResourceButton.clicked.connect( self.__showTaskResourcesClicked )

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
                self.gui.ui.renderTaskTableWidget.item( i, 1 ).setText( tasks[ taskID ].status )
                progressBarInBoxLayout = self.gui.ui.renderTaskTableWidget.cellWidget( i, 2 )
                layout = progressBarInBoxLayout.layout()
                pb = layout.itemAt( 0 ).widget()
                pb.setProperty( "value", int( tasks[ taskID ].progress * 100.0 ) )
            else:
                assert False, "Trying to update not added task."
        
    ############################
    # Add task information in gui
    def addTask( self, task ):
        self.__addTask( task.definition.id, task.status )

    ############################
    def updateTaskAdditionalInfo( self, t ):
        from TaskState import TaskState
        assert isinstance( t, TaskState )

        self.gui.ui.minNodePower.setText( "{} ray per pixel".format( t.definition.minPower ) )
        self.gui.ui.minSubtask.setText( "{} pixels".format( t.definition.minSubtask ) )
        self.gui.ui.maxSubtask.setText( "{} pixels".format( t.definition.maxSubtask ) )
        self.gui.ui.subtaskTimeout.setText( "{} minutes".format( int( t.definition.subtaskTimeout / 60.0 ) ) )
        self.gui.ui.resolution.setText( "{} x {}".format( t.definition.resolution[ 0 ], t.definition.resolution[ 1 ] ) )
        self.gui.ui.renderer.setText( "{}".format( t.definition.renderer ) )
        self.gui.ui.algorithmType.setText( "{}".format( t.definition.algorithmType ) )
        self.gui.ui.pixelFilter.setText( "{}".format( t.definition.pixelFilter ) )
        self.gui.ui.samplesPerPixel.setText( "{}".format( t.definition.samplesPerPixelCount ) )
        self.gui.ui.outputFile.setText( "{}".format( t.definition.outputFile ) )
        self.gui.ui.fullTaskTimeout.setText( str( datetime.timedelta( seconds = t.definition.fullTaskTimeout ) ) )
        self.gui.ui.timeStarted.setText( "{}".format( t.timeStarted ) )
        self.currentTaskHighlighted = t

    ############################
    def __addTask( self, id, status ):
        currentRowCount = self.gui.ui.renderTaskTableWidget.rowCount()
        self.gui.ui.renderTaskTableWidget.insertRow( currentRowCount )

        taskTableElem = TaskTableElem( id, status )

        for col in range( 0, 2 ): self.gui.ui.renderTaskTableWidget.setItem( currentRowCount, col, taskTableElem.getColumnItem( col ) )

        self.gui.ui.renderTaskTableWidget.setCellWidget( currentRowCount, 2, taskTableElem.progressBarInBoxLayoutWidget )

        self.updateTaskAdditionalInfo( self.logic.getTask( id ) )


    # SLOTS
    #############################
    def __taskTableRowClicked( self, row, col ):
        if row < self.gui.ui.renderTaskTableWidget.rowCount():
            taskId = self.gui.ui.renderTaskTableWidget.item( row, 0 ).text()
            taskId = "{}".format( taskId )
            t = self.logic.getTask( taskId )
            self.updateTaskAdditionalInfo( t )

    #############################
    def __showNewTaskDialogClicked( self ):
        self.newTaskDialog = NewTaskDialog( self.gui.window )

        self.newTaskDialogCustomizer = NewTaskDialogCustomizer( self.newTaskDialog, self.logic )

        self.newTaskDialog.show()

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

            for r in res:
                splited = r.split("\\")

                insertItem( item, splited )

            self.showTaskResourcesDialog.ui.folderTreeWidget.expandAll()

        self.showTaskResourcesDialog.show()




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
