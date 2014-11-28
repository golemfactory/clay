import os
import cPickle as pickle
import datetime
from PyQt4 import QtCore
from PyQt4.QtGui import QPixmap, QTreeWidgetItem, QMenu, QFileDialog, QMessageBox, QPalette

from examples.gnr.ui.MainWindow import GNRMainWindow
from examples.gnr.ui.NewTaskDialog import NewTaskDialog
from examples.gnr.ui.ShowTaskResourcesDialog import ShowTaskResourcesDialog
from examples.gnr.ui.TaskDetailsDialog import TaskDetailsDialog
from examples.gnr.ui.SubtaskDetailsDialog import SubtaskDetailsDialog
from examples.gnr.ui.TaskTableElem import TaskTableElem
from examples.gnr.ui.ConfigurationDialog import ConfigurationDialog
from examples.gnr.ui.StatusWindow import StatusWindow
from examples.gnr.ui.ChangeTaskDialog import ChangeTaskDialog
from examples.gnr.ui.InfoTaskDialog import InfoTaskDialog
from examples.gnr.ui.EnvironmentsDialog import EnvironmentsDialog
from examples.gnr.RenderingDirManager import getPreviewFile
from examples.gnr.TaskState import TaskDefinition

from NewTaskDialogCustomizer import NewTaskDialogCustomizer
from TaskContexMenuCustomizer import TaskContextMenuCustomizer
from TaskDetailsDialogCustomizer import TaskDetailsDialogCustomizer
from SubtaskDetailsDialogCustomizer import SubtaskDetailsDialogCustomizer
from ConfigurationDialogCustomizer import ConfigurationDialogCustomizer
from StatusWindowCustomizer import StatusWindowCustomizer
from ChangeTaskDialogCustomizer import ChangeTaskDialogCustomizer
from InfoTaskDialogCustomizer import InfoTaskDialogCustomizer
from EnvironmentsDialogCustomizer import EnvironmentsDialogCustomizer
from MemoryHelper import resourceSizeToDisplay, translateResourceIndex

from golem.task.TaskState import SubtaskStatus

import time
import logging

logger = logging.getLogger(__name__)

frameRenderers = [ u"MentalRay", u"VRay" ]

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
        self.previewPath = os.path.join( os.environ.get('GOLEM'), "examples\\gnr", getPreviewFile() )
        self.sliderPreviews = {}

        palette = QPalette()
        palette.setColor( QPalette.Foreground, QtCore.Qt.red )
        self.gui.ui.errorLabel.setPalette( palette )
        self.gui.ui.frameSlider.setVisible( False )

    #############################
    def __setupConnections( self ):
        self.gui.ui.actionNew.triggered.connect( self.__showNewTaskDialogClicked )
        self.gui.ui.actionLoadTask.triggered.connect( self.__loadTaskButtonClicked )
        self.gui.ui.actionEdit.triggered.connect( self.__showConfigurationDialogClicked )
        self.gui.ui.actionStatus.triggered.connect( self.__showStatusClicked )
        self.gui.ui.actionStartNodesManager.triggered.connect( self.__startNodesManager )
        self.gui.ui.actionSendInfoTask.triggered.connect( self.__showInfoTaskDialog )
        self.gui.ui.actionEnvironments.triggered.connect( self.__showEnvironments )
        QtCore.QObject.connect( self.gui.ui.renderTaskTableWidget, QtCore.SIGNAL( "cellClicked(int, int)" ), self.__taskTableRowClicked )
        QtCore.QObject.connect( self.gui.ui.renderTaskTableWidget, QtCore.SIGNAL( "doubleClicked(const QModelIndex)" ), self.__taskTableRowDoubleClicked )
        self.gui.ui.showResourceButton.clicked.connect( self.__showTaskResourcesClicked )
        self.gui.ui.renderTaskTableWidget.customContextMenuRequested.connect( self.__contexMenuRequested )
        QtCore.QObject.connect( self.gui.ui.frameSlider, QtCore.SIGNAL( "valueChanged( int )" ), self.__updateSliderPreview )
        QtCore.QObject.connect( self.gui.ui.outputFile, QtCore.SIGNAL( "mouseReleaseEvent( int, int, QMouseEvent )" ), self.__openOutputFile )
        QtCore.QObject.connect( self.gui.ui.previewLabel, QtCore.SIGNAL( "mouseReleaseEvent( int, int, QMouseEvent )" ), self.__pixmapClicked )

    ############################
    # Add new task to golem client
    def enqueueNewTask( self, uiNewTaskInfo ):
        self.logic.enqueueNewTask( uiNewTaskInfo )

    ############################
    # Updates tasks information in gui
    def updateTasks( self, tasks ):
        for i in range( self.gui.ui.renderTaskTableWidget.rowCount() ):
            taskId = self.gui.ui.renderTaskTableWidget.item( i, 0 ).text()
            taskId = "{}".format( taskId )
            if taskId in tasks:
                self.gui.ui.renderTaskTableWidget.item( i, 1 ).setText( tasks[ taskId ].taskState.status )
                progressBarInBoxLayout = self.gui.ui.renderTaskTableWidget.cellWidget( i, 2 )
                layout = progressBarInBoxLayout.layout()
                pb = layout.itemAt( 0 ).widget()
                pb.setProperty( "value", int( tasks[ taskId ].taskState.progress * 100.0 ) )
                if self.taskDetailsDialogCustomizer:
                    if self.taskDetailsDialogCustomizer.gnrTaskState.definition.taskId == taskId:
                        self.taskDetailsDialogCustomizer.updateView( tasks[ taskId ].taskState )

            else:
                assert False, "Trying to update not added task."
        
    ############################
    # Add task information in gui
    def addTask( self, task ):
        self.__addTask( task.definition.taskId, task.status )

    ############################
    def updateTaskAdditionalInfo( self, t ):
        from examples.gnr.TaskState import GNRTaskState
        assert isinstance( t, GNRTaskState )

        self.currentTaskHighlighted = t
        self.gui.ui.subtaskTimeout.setText( "{} minutes".format( int( t.definition.subtaskTimeout / 60.0 ) ) )
        self.gui.ui.fullTaskTimeout.setText( str( datetime.timedelta( seconds = t.definition.fullTaskTimeout ) ) )
        if t.taskState.timeStarted != 0.0:
            lt = time.localtime( t.taskState.timeStarted )
            timeString  = time.strftime( "%Y.%m.%d  %H:%M:%S", lt )
            self.gui.ui.timeStarted.setText( timeString )

        if not isinstance( t.definition, TaskDefinition ):
            return
        mem, index = resourceSizeToDisplay( t.definition.estimatedMemory / 1024 )
        self.gui.ui.estimatedMemoryLabel.setText( "{} {}".format( mem, translateResourceIndex( index ) ) )
        self.gui.ui.resolution.setText( "{} x {}".format( t.definition.resolution[ 0 ], t.definition.resolution[ 1 ] ) )
        self.gui.ui.renderer.setText( "{}".format( t.definition.renderer ) )
        if t.definition.renderer == u"PBRT":
            self.gui.ui.algorithmType.setText( "{}".format( t.definition.rendererOptions.algorithmType ) )
            self.gui.ui.algorithmTypeLabel.setVisible( True )
            self.gui.ui.pixelFilter.setText( "{}".format( t.definition.rendererOptions.pixelFilter ) )
            self.gui.ui.pixelFilterLabel.setVisible( True )
            self.gui.ui.samplesPerPixel.setText( "{}".format( t.definition.rendererOptions.samplesPerPixelCount ) )
            self.gui.ui.samplesPerPixelLabel.setVisible( True )
        else:
            self.gui.ui.algorithmType.setText( "" )
            self.gui.ui.algorithmTypeLabel.setVisible( False )
            self.gui.ui.pixelFilter.setText( "" )
            self.gui.ui.pixelFilterLabel.setVisible( False )
            self.gui.ui.samplesPerPixel.setText( "" )
            self.gui.ui.samplesPerPixelLabel.setVisible( False )


        if t.definition.renderer in frameRenderers and t.definition.rendererOptions.useFrames:
            if "resultPreview" in t.taskState.extraData:
                self.sliderPreviews = t.taskState.extraData[ "resultPreview" ]
            self.gui.ui.frameSlider.setVisible( True )
            self.gui.ui.frameSlider.setRange( 1, len( t.definition.rendererOptions.frames ) )
            self.gui.ui.frameSlider.setSingleStep( 1 )
            self.gui.ui.frameSlider.setPageStep( 1 )
            self.__updateSliderPreview()
        else:
            self.gui.ui.frameSlider.setVisible( False )
            if "resultPreview" in t.taskState.extraData:
                filePath = os.path.abspath( t.taskState.extraData["resultPreview"] )
                if os.path.exists( filePath ):
                    self.gui.ui.previewLabel.setPixmap( QPixmap( filePath ) )
            else:
                self.gui.ui.previewLabel.setPixmap( QPixmap( self.previewPath ) )
        self.gui.ui.outputFile.setText( u"{}".format( t.definition.outputFile ) )
        if os.path.isfile( t.definition.outputFile ):
            self.gui.ui.outputFile.setStyleSheet( 'color: blue' )
        else:
            self.gui.ui.outputFile.setStyleSheet( 'color: black' )

        self.currentTaskHighlighted = t

    ############################
    def __addTask( self, taskId, status ):
        currentRowCount = self.gui.ui.renderTaskTableWidget.rowCount()
        self.gui.ui.renderTaskTableWidget.insertRow( currentRowCount )

        taskTableElem = TaskTableElem( taskId, status )

        for col in range( 0, 2 ): self.gui.ui.renderTaskTableWidget.setItem( currentRowCount, col, taskTableElem.getColumnItem( col ) )

        self.gui.ui.renderTaskTableWidget.setCellWidget( currentRowCount, 2, taskTableElem.progressBarInBoxLayoutWidget )

        self.gui.ui.renderTaskTableWidget.setCurrentItem( self.gui.ui.renderTaskTableWidget.item( currentRowCount, 1) )
        self.updateTaskAdditionalInfo( self.logic.getTask( taskId ) )

    ############################
    def removeTask( self, taskId ):

        for row in range(0, self.gui.ui.renderTaskTableWidget.rowCount()):
            if self.gui.ui.renderTaskTableWidget.item(row, 0).text() == taskId:
                self.gui.ui.renderTaskTableWidget.removeRow( row )
                return

    ############################
    def __loadTaskButtonClicked( self ):
        golemPath = os.environ.get( 'GOLEM' )
        dir = ""
        if golemPath:
            saveDir = os.path.join( golemPath, "save" )
            if os.path.isdir( saveDir ):
                dir = saveDir

        fileName = QFileDialog.getOpenFileName( self.gui.window,
            "Choose task file", dir, "Golem Task (*.gt)")
        if os.path.exists( fileName ):
            self.__loadTask( fileName )

    ############################
    def __startNodesManager( self ):
        self.logic.startNodesManagerServer()

    ############################
    def __sendInfoTask( self ):
        self.logic.sendInfoTask()


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

    #############################
    def showSubtaskDetailsDialog( self, subtask ):
        subtaskDetailsDialog = SubtaskDetailsDialog( self.gui.window )
        subtaskDetailsDialogCustomizer = SubtaskDetailsDialogCustomizer( subtaskDetailsDialog, self.logic, subtask )
        subtaskDetailsDialog.show()
    #############################
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
    def __showInfoTaskDialog( self ):
        self.infoTaskDialog = InfoTaskDialog( self.gui.window )
        self.infoTaskDialogCustomizer = InfoTaskDialogCustomizer( self.infoTaskDialog, self.logic )
     #   self.infoTaskDialogCustomizer.loadDefaults()
        self.infoTaskDialog.show()

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

    #############################
    def __showEnvironments ( self ):
        self.environmentsDialog = EnvironmentsDialog( self.gui.window )

        self.environmentsDialogCustomizer = EnvironmentsDialogCustomizer( self.environmentsDialog, self.logic )
        self.environmentsDialog.show()

    #############################
    def __updateSliderPreview( self ):
        num = self.gui.ui.frameSlider.value() - 1
        if len( self.sliderPreviews ) > num:
            if self.sliderPreviews[ num ]:
                if os.path.exists ( self.sliderPreviews [ num ]):
                    self.gui.ui.previewLabel.setPixmap( QPixmap( self.sliderPreviews[ num ] ) )
                    return

        self.gui.ui.previewLabel.setPixmap( QPixmap( self.previewPath ) )

    #############################
    def __openOutputFile( self ):
        file = self.gui.ui.outputFile.text()
        if os.path.isfile( file ):
            os.startfile( file )

    #############################
    def __pixmapClicked( self, x, y, *args ):
        if self.currentTaskHighlighted and self.currentTaskHighlighted.definition.renderer:
            definition = self.currentTaskHighlighted.definition
            taskId = definition.taskId
            task =  self.logic.getTask( taskId )
            renderer = self.logic.getRenderer( definition.renderer )
            if len( task.taskState.subtaskStates ) > 0:
                totalTasks = task.taskState.subtaskStates.values()[0].extraData['totalTasks']
                if definition.renderer in frameRenderers and definition.rendererOptions.useFrames:
                    frames = len ( definition.rendererOptions.frames )
                    frameNum = self.gui.ui.frameSlider.value()
                    num = renderer.getTaskNumFromPixels( x, y, totalTasks, useFrames = True, frames = frames, frameNum = frameNum )
                else:
                    num = renderer.getTaskNumFromPixels( x, y, totalTasks )
                if num is not None:
                    subtasks = [ sub  for sub in task.taskState.subtaskStates.values() if sub.extraData['startTask']  <= num <= sub.extraData['endTask']  ]
                    if len( subtasks ) > 0:
                        subtask = min( subtasks, key=lambda x: subtasksPriority( x ) )
                        self.showSubtaskDetailsDialog( subtask )

#######################################################################################
def insertItem( root, pathTable ):
    assert isinstance( root, QTreeWidgetItem )

    if len( pathTable ) > 0:
        for i in range( root.childCount() ):
            if pathTable[ 0 ] == "{}".format( root.child( i ).text( 0 ) ):
                insertItem( root.child( i ), pathTable[ 1: ] )
                return

        newChild = QTreeWidgetItem( [ pathTable[ 0 ] ] )
        root.addChild( newChild )
        insertItem( newChild, pathTable[ 1: ] )

def subtasksPriority( sub ):
    priority = {
        SubtaskStatus.failure: 5,
        SubtaskStatus.resent: 4,
        SubtaskStatus.finished: 3,
        SubtaskStatus.starting: 2,
        SubtaskStatus.waiting: 1 }

    return priority[ sub.subtaskStatus ]

