import os
import datetime
import time
import logging
from PyQt4 import QtCore
from PyQt4.QtGui import QPixmap, QTreeWidgetItem, QPainter, QColor, QPen, QMessageBox

from golem.task.TaskState import SubtaskStatus

from examples.gnr.ui.ShowTaskResourcesDialog import ShowTaskResourcesDialog
from examples.gnr.ui.RenderingNewTaskDialog import NewTaskDialog

from examples.gnr.RenderingDirManager import getPreviewFile
from examples.gnr.RenderingTaskState import RenderingTaskDefinition

from examples.gnr.customizers.GNRMainWindowCustomizer import GNRMainWindowCustomizer
from examples.gnr.customizers.GNRAdministratorMainWindowCustomizer import GNRAdministratorMainWindowCustomizer
from examples.gnr.customizers.RenderingNewTaskDialogCustomizer import RenderingNewTaskDialogCustomizer

from examples.gnr.customizers.MemoryHelper import resourceSizeToDisplay, translateResourceIndex

logger = logging.getLogger(__name__)

#######################################################################################
frameRenderers = [ u"3ds Max Renderer", u"VRay Standalone", u"Blender" ]

#######################################################################################
def subtasksPriority( sub ):
    priority = {
        SubtaskStatus.failure: 5,
        SubtaskStatus.resent: 4,
        SubtaskStatus.finished: 3,
        SubtaskStatus.starting: 2,
        SubtaskStatus.waiting: 1 }

    return priority[ sub.subtaskStatus ]

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

#######################################################################################
class AbsRenderingMainWindowCustomizer ( object ):
    ############################
    def _setRenderingVariables( self ):
        self.previewPath = os.path.join( os.environ.get('GOLEM'), "examples\\gnr", getPreviewFile() )
        self.lastPreviewPath = self.previewPath
        self.sliderPreviews = {}
        self.gui.ui.frameSlider.setVisible( False )

    #############################

    def _setupRenderingConnections( self ):
        QtCore.QObject.connect( self.gui.ui.frameSlider, QtCore.SIGNAL( "valueChanged( int )" ), self.__updateSliderPreview )
        QtCore.QObject.connect( self.gui.ui.outputFile, QtCore.SIGNAL( "mouseReleaseEvent( int, int, QMouseEvent )" ), self.__openOutputFile )
        QtCore.QObject.connect( self.gui.ui.previewLabel, QtCore.SIGNAL( "mouseReleaseEvent( int, int, QMouseEvent )" ), self.__pixmapClicked )
        self.gui.ui.previewLabel.setMouseTracking( True )
        QtCore.QObject.connect( self.gui.ui.previewLabel, QtCore.SIGNAL( "mouseMoveEvent( int, int, QMouseEvent )" ), self.__mouseOnPixmapMoved )

    def _setupAdvanceTaskConnections( self ):
        self.gui.ui.showResourceButton.clicked.connect( self._showTaskResourcesClicked )

    ############################
    def _setNewTaskDialog( self ):
        self.newTaskDialog = NewTaskDialog( self.gui.window )

    ############################
    def _setNewTaskDialogCustomizer( self ):
        self.newTaskDialogCustomizer = RenderingNewTaskDialogCustomizer( self.newTaskDialog, self.logic )

    ############################
    def updateTaskAdditionalInfo( self, t ):
        from examples.gnr.RenderingTaskState import RenderingTaskState
        assert isinstance( t, RenderingTaskState )

        self.currentTaskHighlighted = t
        self.__setTimeParams( t )

        if not isinstance( t.definition, RenderingTaskDefinition ):
            return

        self.__setRendererParams( t )
        self.__setPBRTParams( t, isPBRT=( t.definition.renderer == u"PBRT")  )

        if t.definition.renderer in frameRenderers and t.definition.rendererOptions.useFrames:
            self.__setFramePreview( t )
        else:
            self.__setPreview( t )

        self.__updateOutputFileColor()
        self.currentTaskHighlighted = t

    #############################
    def showTaskResult( self, taskId ):
        t = self.logic.getTask( taskId )
        if t.definition.renderer in frameRenderers and t.definition.rendererOptions.useFrames:
            file_ = self.__getFrameName( t.definition, 0 )
        else:
            file_ = t.definition.outputFile
        if os.path.isfile( file_ ):
                self._showFile( file_ )
        else:
            msgBox = QMessageBox()
            msgBox.setText("No output file defined.")
            msgBox.exec_()

    ############################
    def __setTimeParams( self, t ):
        self.gui.ui.subtaskTimeout.setText( "{} minutes".format( int( t.definition.subtaskTimeout / 60.0 ) ) )
        self.gui.ui.fullTaskTimeout.setText( str( datetime.timedelta( seconds = t.definition.fullTaskTimeout ) ) )
        if t.taskState.timeStarted != 0.0:
            lt = time.localtime( t.taskState.timeStarted )
            timeString  = time.strftime( "%Y.%m.%d  %H:%M:%S", lt )
            self.gui.ui.timeStarted.setText( timeString )

    ############################
    def __setRendererParams( self, t ):
        mem, index = resourceSizeToDisplay( t.definition.estimatedMemory / 1024 )
        self.gui.ui.estimatedMemoryLabel.setText( "{} {}".format( mem, translateResourceIndex( index ) ) )
        self.gui.ui.resolution.setText( "{} x {}".format( t.definition.resolution[ 0 ], t.definition.resolution[ 1 ] ) )
        self.gui.ui.renderer.setText( "{}".format( t.definition.renderer ) )

    ############################
    def __setPBRTParams( self, t, isPBRT = True ):
        if isPBRT:
            self.gui.ui.algorithmType.setText( "{}".format( t.definition.rendererOptions.algorithmType ) )
            self.gui.ui.pixelFilter.setText( "{}".format( t.definition.rendererOptions.pixelFilter ) )
            self.gui.ui.samplesPerPixel.setText( "{}".format( t.definition.rendererOptions.samplesPerPixelCount ) )

        self.gui.ui.algorithmType.setVisible( isPBRT )
        self.gui.ui.algorithmTypeLabel.setVisible( isPBRT )
        self.gui.ui.pixelFilter.setVisible( isPBRT )
        self.gui.ui.pixelFilterLabel.setVisible( isPBRT )
        self.gui.ui.samplesPerPixel.setVisible( isPBRT )
        self.gui.ui.samplesPerPixelLabel.setVisible( isPBRT )

    ############################
    def __setFramePreview( self, t ):
        if "resultPreview" in t.taskState.extraData:
            self.sliderPreviews = t.taskState.extraData[ "resultPreview" ]
        self.gui.ui.frameSlider.setVisible( True )
        self.gui.ui.frameSlider.setRange( 1, len( t.definition.rendererOptions.frames ) )
        self.gui.ui.frameSlider.setSingleStep( 1 )
        self.gui.ui.frameSlider.setPageStep( 1 )
        self.__updateSliderPreview()
        firstFrameName = self.__getFrameName( t.definition, 0 )
        self.gui.ui.outputFile.setText( u"{}".format( firstFrameName ) )

    ############################
    def __setPreview( self, t ):
        self.gui.ui.outputFile.setText( u"{}".format( t.definition.outputFile ) )
        self.gui.ui.frameSlider.setVisible( False )
        if "resultPreview" in t.taskState.extraData:
            filePath = os.path.abspath( t.taskState.extraData["resultPreview"] )
            time.sleep(0.5)
            if os.path.exists( filePath ):
                self.gui.ui.previewLabel.setPixmap( QPixmap( filePath ) )
                self.lastPreviewPath = filePath
        else:
            self.gui.ui.previewLabel.setPixmap( QPixmap( self.previewPath ) )
            self.lastPreviewPath = self.previewPath


    ############################
    def __getFrameName( self, definition, num ):
        outputName, ext = os.path.splitext( definition.outputFile )
        frameNum = definition.rendererOptions.frames[ num ]
        outputName += str(frameNum).zfill(4)
        return outputName + ext

    ############################
    def __updateOutputFileColor( self ):
        if os.path.isfile( self.gui.ui.outputFile.text() ):
            self.gui.ui.outputFile.setStyleSheet( 'color: blue' )
        else:
            self.gui.ui.outputFile.setStyleSheet( 'color: black' )

    #############################
    def _showTaskResourcesClicked( self ):

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

    #############################
    def __updateSliderPreview( self ):
        num = self.gui.ui.frameSlider.value() - 1
        self.gui.ui.outputFile.setText( self.__getFrameName( self.currentTaskHighlighted.definition, num ))
        self.__updateOutputFileColor()
        if len( self.sliderPreviews ) > num:
            if self.sliderPreviews[ num ]:
                if os.path.exists ( self.sliderPreviews [ num ]):
                    self.gui.ui.previewLabel.setPixmap( QPixmap( self.sliderPreviews[ num ] ) )
                    self.lastPreviewPath = self.sliderPreviews[ num ]
                    return

        self.gui.ui.previewLabel.setPixmap( QPixmap( self.previewPath ) )
        self.lastPreviewPath = self.previewPath

    #############################
    def __openOutputFile( self ):
        file_ = self.gui.ui.outputFile.text()
        if os.path.isfile( file_ ):
            self._showFile( file_ )

    #############################
    def __getTaskNumFromPixels(self, x, y ):
        num = None

        t = self.currentTaskHighlighted
        if t is None or not isinstance( t.definition, RenderingTaskDefinition ):
            return

        if t.definition.renderer:
            definition = t.definition
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
        return num

    #############################
    def __getSubtask( self, num ):
        subtask = None
        task = self.logic.getTask( self.currentTaskHighlighted.definition.taskId )
        subtasks = [ sub  for sub in task.taskState.subtaskStates.values() if sub.extraData['startTask']  <= num <= sub.extraData['endTask']  ]
        if len( subtasks ) > 0:
                subtask = min( subtasks, key=lambda x: subtasksPriority( x ) )
        return subtask

    #############################
    def __pixmapClicked( self, x, y, *args ):
        num = self.__getTaskNumFromPixels(x, y)
        if num is not None:
            subtask = self.__getSubtask( num )
            if subtask is not None:
                self.showSubtaskDetailsDialog( subtask )

    #############################
    def __mouseOnPixmapMoved(self, x, y, *args ):
        num = self.__getTaskNumFromPixels(x, y)
        if num is not None:
            definition = self.currentTaskHighlighted.definition
            if not isinstance( definition, RenderingTaskDefinition ):
                return
            renderer = self.logic.getRenderer( definition.renderer )
            subtask = self.__getSubtask( num )
            if subtask is not None:
                if definition.renderer in frameRenderers and definition.rendererOptions.useFrames:
                    frames = len ( definition.rendererOptions.frames )
                    frameNum = self.gui.ui.frameSlider.value()
                    border = renderer.getTaskBoarder( subtask.extraData['startTask'],
                                                       subtask.extraData['endTask'],
                                                       subtask.extraData['totalTasks'],
                                                       self.currentTaskHighlighted.definition.resolution[0],
                                                       self.currentTaskHighlighted.definition.resolution[1],
                                                       useFrames = True,
                                                       frames = frames,
                                                       frameNum = frameNum )
                else:
                    border = renderer.getTaskBoarder( subtask.extraData['startTask'],
                                                       subtask.extraData['endTask'],
                                                       subtask.extraData['totalTasks'],
                                                       self.currentTaskHighlighted.definition.resolution[0],
                                                       self.currentTaskHighlighted.definition.resolution[1])

                if os.path.isfile( self.lastPreviewPath ):
                    self.__drawBoarder( border )

    def __drawBoarder(self, border ):
        pixmap = QPixmap( self.lastPreviewPath )
        p = QPainter( pixmap )
        pen = QPen( QColor( 0, 0, 0 ))
        pen.setWidth( 3 )
        p.setPen( pen )
        for (x, y) in border:
            p.drawPoint( x, y )
        p.end()
        self.gui.ui.previewLabel.setPixmap( pixmap )

class RenderingMainWindowCustomizer( AbsRenderingMainWindowCustomizer, GNRMainWindowCustomizer ):
    def __init__( self, gui, logic ):
        GNRMainWindowCustomizer.__init__( self, gui, logic )
        self._setRenderingVariables()
        self._setupRenderingConnections()
        self._setupAdvanceTaskConnections()



