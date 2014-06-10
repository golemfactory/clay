import os
import datetime
from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog, QTreeWidgetItem, QMenu, QAction

from ui.MainWindow import GNRMainWindow
from ui.NewTaskDialog import NewTaskDialog
from ui.ShowTaskResourcesDialog import ShowTaskResourcesDialog
from ui.TaskDetailsDialog import TaskDetailsDialog
from ui.TaskTableElem import TaskTableElem

from NewTaskDialogCustomizer import NewTaskDialogCustomizer
from TaskContexMenuCustomizer import TaskContextMenuCustomizer
from TaskDetailsDialogCustomizer import TaskDetailsDialogCustomizer




class MainWindowCustomizer:
    ############################
    def __init__( self, gui, logic ):

        assert isinstance( gui, GNRMainWindow )

        self.gui    = gui
        self.logic  = logic

        self.__setupConnections()
        self.currentTaskHighlighted = None
        self.taskDetailsDialog      = None

    #############################
    def __setupConnections( self ):
        self.gui.ui.actionNew.triggered.connect( self.__showNewTaskDialogClicked )
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
        self.gui.ui.outputFile.setText( "{}".format( t.definition.outputFile ) )
        self.gui.ui.fullTaskTimeout.setText( str( datetime.timedelta( seconds = t.definition.fullTaskTimeout ) ) )
        self.gui.ui.timeStarted.setText( "{}".format( t.taskState.timeStarted ) )
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
    def __showTaskContextMenu( self, p ):
 
        row = self.gui.ui.renderTaskTableWidget.itemAt( p ).row()

        print "{}".format( row )

        idItem = self.gui.ui.renderTaskTableWidget.item( row, 0 )

        taskId = "{}".format( idItem.text() )

        ts = self.logic.getTask( taskId )

        print "{}".format( taskId )

        menu = QMenu()

        self.taskContextMenuCustomizer =  TaskContextMenuCustomizer( menu, self.logic, ts )

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
    def __taskTableRowDoubleClicked( self, m ):
        row = m.row()
        taskId = "{}".format( self.gui.ui.renderTaskTableWidget.item( row, 0 ).text() )
        ts = self.logic.getTask( taskId )
        self.taskDetailsDialog = TaskDetailsDialog( self.gui.window )
        self.taskDetailsDialogCustomizer = TaskDetailsDialogCustomizer( self.taskDetailsDialog, self.logic, ts )
        self.taskDetailsDialog.show()

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

