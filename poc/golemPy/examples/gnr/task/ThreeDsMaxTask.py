import logging
import random
import os
import math

from PIL import Image, ImageChops

from golem.task.TaskState import SubtaskStatus

from examples.gnr.task.GNRTask import  GNROptions, checkSubtaskIdWrapper
from examples.gnr.task.RenderingTaskCollector import exr_to_pil
from examples.gnr.task.FrameRenderingTask import FrameRenderingTask, FrameRenderingTaskBuiler, getTaskBoarder, getTaskNumFromPixels
from examples.gnr.RenderingDirManager import getTestTaskPath, getTmpPath
from examples.gnr.RenderingTaskState import RendererDefaults, RendererInfo
from examples.gnr.RenderingEnvironment import ThreeDSMaxEnvironment
from examples.gnr.ui.ThreeDSMaxDialog import ThreeDSMaxDialog
from examples.gnr.customizers.ThreeDSMaxDialogCustomizer import ThreeDSMaxDialogCustomizer

logger = logging.getLogger(__name__)

##############################################
def build3dsMaxRendererInfo():
    defaults = RendererDefaults()
    defaults.outputFormat       = "EXR"
    defaults.mainProgramFile    = os.path.normpath( os.path.join( os.environ.get( 'GOLEM' ), 'examples\\tasks\\3dsMaxTask.py' ) )
    defaults.minSubtasks        = 1
    defaults.maxSubtasks        = 100
    defaults.defaultSubtasks    = 6

    renderer                = RendererInfo( "3ds Max Renderer", defaults, ThreeDSMaxTaskBuilder, ThreeDSMaxDialog, ThreeDSMaxDialogCustomizer, ThreeDSMaxRendererOptions )
    renderer.outputFormats  = [ "BMP", "EXR", "GIF", "IM", "JPEG", "PCD", "PCX", "PNG", "PPM", "PSD", "TIFF", "XBM", "XPM" ]
    renderer.sceneFileExt   = [ "max",  "zip" ]
    renderer.getTaskNumFromPixels = getTaskNumFromPixels
    renderer.getTaskBoarder = getTaskBoarder

    return renderer

##############################################
class ThreeDSMaxRendererOptions ( GNROptions ):
    #######################
    def __init__( self ):
        self.environment = ThreeDSMaxEnvironment()
        self.preset = self.environment.getDefaultPreset()
        self.cmd = self.environment.get3dsmaxcmdPath()
        self.useFrames = False
        self.frames = range(1, 11)

    #######################
    def addToResources( self, resources ):
        if os.path.isfile( self.preset ):
            resources.add( os.path.normpath( self.preset ) )
        return resources

    #######################
    def removeFromResources( self, resources ):
        if os.path.normpath( self.preset ) in resources:
            resources.remove( os.path.normpath( self.preset ) )
        return resources

##############################################
class ThreeDSMaxTaskBuilder( FrameRenderingTaskBuiler ):
    #######################
    def build( self ):
        mainSceneDir = os.path.dirname( self.taskDefinition.mainSceneFile )

        threeDSMaxTask = ThreeDSMaxTask(self.clientId,
                                   self.taskDefinition.taskId,
                                   mainSceneDir,
                                   self.taskDefinition.mainSceneFile,
                                   self.taskDefinition.mainProgramFile,
                                   self._calculateTotal( build3dsMaxRendererInfo(), self.taskDefinition ),
                                   self.taskDefinition.resolution[0],
                                   self.taskDefinition.resolution[1],
                                   os.path.splitext( os.path.basename( self.taskDefinition.outputFile ) )[0],
                                   self.taskDefinition.outputFile,
                                   self.taskDefinition.outputFormat,
                                   self.taskDefinition.fullTaskTimeout,
                                   self.taskDefinition.subtaskTimeout,
                                   self.taskDefinition.resources,
                                   self.taskDefinition.estimatedMemory,
                                   self.rootPath,
                                   self.taskDefinition.rendererOptions.preset,
                                   self.taskDefinition.rendererOptions.cmd,
                                   self.taskDefinition.rendererOptions.useFrames,
                                   self.taskDefinition.rendererOptions.frames
                                   )

        return self._setVerificationOptions( threeDSMaxTask )


##############################################
class ThreeDSMaxTask( FrameRenderingTask ):

    #######################
    def __init__( self,
                  clientId,
                  taskId,
                  mainSceneDir,
                  mainSceneFile,
                  mainProgramFile,
                  totalTasks,
                  resX,
                  resY,
                  outfilebasename,
                  outputFile,
                  outputFormat,
                  fullTaskTimeout,
                  subtaskTimeout,
                  taskResources,
                  estimatedMemory,
                  rootPath,
                  presetFile,
                  cmdFile,
                  useFrames,
                  frames,
                  returnAddress = "",
                  returnPort = 0,
                  ):

        FrameRenderingTask.__init__( self, clientId, taskId, returnAddress, returnPort,
                          ThreeDSMaxEnvironment.getId(), fullTaskTimeout, subtaskTimeout,
                          mainProgramFile, taskResources, mainSceneDir, mainSceneFile,
                          totalTasks, resX, resY, outfilebasename, outputFile, outputFormat,
                          rootPath, estimatedMemory, useFrames, frames )


        self.presetFile = presetFile
        self.cmd        = cmdFile
        self.framesGiven = {}

    #######################
    def queryExtraData( self, perfIndex, numCores = 0, clientId = None ):

        if not self._acceptClient( clientId ):
            logger.warning(" Client {} banned from this task ".format( clientId ) )
            return None

        startTask, endTask = self._getNextTask()

        workingDirectory = self._getWorkingDirectory()
        presetFile = self.__getPresetFileRelPath()
        sceneFile = self._getSceneFileRelPath()
        cmdFile = os.path.basename( self.cmd )

        if self.useFrames:
            frames, parts = self._chooseFrames( self.frames, startTask, self.totalTasks )
        else:
            frames = []
            parts = 1

        extraData =          {      "pathRoot" : self.mainSceneDir,
                                    "startTask" : startTask,
                                    "endTask" : endTask,
                                    "totalTasks" : self.totalTasks,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFile" : sceneFile,
                                    "width" : self.resX,
                                    "height": self.resY,
                                    "presetFile": presetFile,
                                    "cmdFile": cmdFile,
                                    "numCores": numCores,
                                    "useFrames": self.useFrames,
                                    "frames": frames,
                                    "parts": parts,
                                    "overlap": 0
                                }



        hash = "{}".format( random.getrandbits(128) )
        self.subTasksGiven[ hash ] = extraData
        self.subTasksGiven[ hash ]['status' ] = SubtaskStatus.starting
        self.subTasksGiven[ hash ]['perf'] = perfIndex
        self.subTasksGiven[ hash ][ 'clientId' ] = clientId

        for frame in frames:
            self.framesGiven[ frame ] = {}

        if not self.useFrames:
            self._updateTaskPreview()
        else:
            self._updateFrameTaskPreview()

        return self._newComputeTaskDef( hash, extraData, workingDirectory, perfIndex )

    #######################
    def queryExtraDataForTestTask( self ):

        workingDirectory = self._getWorkingDirectory()
        presetFile = self.__getPresetFileRelPath()
        sceneFile = self._getSceneFileRelPath()
        cmdFile = os.path.basename( self.cmd )

        if self.useFrames:
            frames = [ self.frames[0] ]
        else:
            frames = []

        extraData =          {      "pathRoot" : self.mainSceneDir,
                                    "startTask" : 1,
                                    "endTask" : 1,
                                    "totalTasks" : self.totalTasks,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFile" : sceneFile,
                                    "width" : 1,
                                    "height": self.totalTasks,
                                    "presetFile": presetFile,
                                    "cmdFile": cmdFile,
                                    "numCores": 0,
                                    "useFrames": self.useFrames,
                                    "frames": frames, 
                                    "parts": 1,
                                    "overlap": 0
                                }

        hash = "{}".format( random.getrandbits(128) )

        self.testTaskResPath = getTestTaskPath( self.rootPath )
        logger.debug( self.testTaskResPath )
        if not os.path.exists( self.testTaskResPath ):
            os.makedirs( self.testTaskResPath )

        return self._newComputeTaskDef( hash, extraData, workingDirectory, 0 )

  #######################
    @checkSubtaskIdWrapper
    def computationFinished( self, subtaskId, taskResult, dirManager = None, resultType = 0 ):

        if not self.shouldAccept( subtaskId ):
            return

        tmpDir = dirManager.getTaskTemporaryDir( self.header.taskId, create = False )
        self.tmpDir = tmpDir


        if len( taskResult ) > 0:
            numStart = self.subTasksGiven[ subtaskId ][ 'startTask' ]
            parts = self.subTasksGiven[ subtaskId ][ 'parts' ]
            numEnd = self.subTasksGiven[ subtaskId ][ 'endTask' ]
            self.subTasksGiven[ subtaskId ][ 'status' ] = SubtaskStatus.finished

            if self.useFrames and self.totalTasks <= len( self.frames ):
                framesList = self.subTasksGiven[ subtaskId ]['frames']
                if len( taskResult ) < len( framesList ):
                    self._markSubtaskFailed( subtaskId )
                    if not self.useFrames:
                        self._updateTaskPreview()
                    else:
                        self._updateFrameTaskPreview()
                    return

            trFiles = self.loadTaskResults( taskResult, resultType, tmpDir )

            if not self._verifyImgs( subtaskId, trFiles ):
                self._markSubtaskFailed( subtaskId )
                if not self.useFrames:
                    self._updateTaskPreview()
                else:
                    self._updateFrameTaskPreview()
                return

            self.countingNodes[ self.subTasksGiven[ subtaskId ][ 'clientId' ] ] = 1

            for trFile in trFiles:

                if not self.useFrames:
                    self._collectImagePart( numStart, trFile )
                elif self.totalTasks <= len( self.frames ):
                    framesList = self._collectFrames( numStart, trFile, framesList, tmpDir )
                else:
                    self._collectFramePart( numStart, trFile, parts, tmpDir )

            self.numTasksReceived += numEnd - numStart + 1

        if self.numTasksReceived == self.totalTasks:
            if self.useFrames:
                self._copyFrames()
            else:
                self._putImageTogether( tmpDir )

    #######################
    @checkSubtaskIdWrapper
    def getPriceMod( self, subtaskId ):
        perf =  (self.subTasksGiven[ subtaskId ]['endTask'] - self.subTasksGiven[ subtaskId ][ 'startTask' ]) + 1
        perf *= float( self.subTasksGiven[ subtaskId ]['perf'] ) / 1000
        perf *= 50
        return perf

    #######################
    @checkSubtaskIdWrapper
    def restartSubtask( self, subtaskId ):
        FrameRenderingTask.restartSubtask( self, subtaskId )
        if not self.useFrames:
            self._updateTaskPreview()
        else:
            self._updateFrameTaskPreview()

    #######################
    def _updatePreview( self, newChunkFilePath, chunkNum ):

        if newChunkFilePath.endswith(".exr"):
            img = exr_to_pil( newChunkFilePath )
        else:
            img = Image.open( newChunkFilePath )

        imgOffset = Image.new("RGB", (self.resX, self.resY) )
        try:
            offset = int (math.floor( (chunkNum - 1) * float( self.resY ) / float( self.totalTasks ) ) )
            imgOffset.paste(img, ( 0, offset ) )
        except Exception, err:
            logger.error("Can't generate preview {}".format( str(err) ))

        tmpDir = getTmpPath( self.header.clientId, self.header.taskId, self.rootPath )

        self.previewFilePath = "{}".format( os.path.join( tmpDir, "current_preview") )

        if os.path.exists( self.previewFilePath ):
            imgCurrent = Image.open( self.previewFilePath )
            imgCurrent = ImageChops.add( imgCurrent, imgOffset )
            imgCurrent.save( self.previewFilePath, "BMP" )
        else:
            imgOffset.save( self.previewFilePath, "BMP" )


    #######################
    def _shortExtraDataRepr( self, perfIndex, extraData ):
        l = extraData
        msg = []
        msg.append( "scene file: {} ".format( l [ "sceneFile" ] ) )
        msg.append( "preset: {} ".format( l [ "presetFile" ] ) )
        msg.append( "total tasks: {}".format( l[ "totalTasks" ] ) )
        msg.append( "start task: {}".format( l[ "startTask" ] ) )
        msg.append( "end task: {}".format( l[ "endTask" ] ) )
        msg.append( "outfile basename: {}".format( l[ "outfilebasename" ] ) )
        msg.append( "size: {}x{}".format( l[ "width" ], l[ "height" ] ) )
        if l["useFrames"]:
            msg.append( "frames: {}".format( l[ "frames" ] ) )
        return "\n".join( msg )


    #######################
    def _getOutputName( self, frameNum, numStart ):
        num = str( frameNum )
        return "{}{}.{}".format( self.outfilebasename, num.zfill(4), self.outputFormat )

    #######################
    def __getPresetFileRelPath( self ):
        presetFile = os.path.relpath( os.path.dirname( self.presetFile ), os.path.dirname( self.mainProgramFile ) )
        presetFile = os.path.join( presetFile, os.path.basename( self.presetFile ) )
        return presetFile

    #######################
    def _getPartSize( self ) :
        if not self.useFrames:
            resY = int (math.floor( float( self.resY ) / float( self.totalTasks ) ) )
        elif len( self.frames ) >= self.totalTasks:
            resY = self.resY
        else:
            parts = self.totalTasks / len( self.frames )
            resY = int (math.floor( float( self.resY ) / float( parts ) ) )
        return self.resX, resY

    #######################
    @checkSubtaskIdWrapper
    def _getPartImgSize( self, subtaskId, advTestFile ) :
        x, y = self._getPartSize()
        return 0, 0, x, y

    #######################
    @checkSubtaskIdWrapper
    def _changeScope( self, subtaskId, startBox, trFile ):
        extraData, _ = FrameRenderingTask._changeScope( self, subtaskId, startBox, trFile )
        if not self.useFrames:
            startY = startBox[1] + (extraData['startTask'] - 1) * self.resY / extraData['totalTasks']
        elif self.totalTasks <= len( self.frames ):
            startY = startBox[1]
            extraData['frames'] = [ self.__getFrameNumFromOutputFile( trFile ) ]
            extraData['parts'] = extraData['totalTasks']
        else:
            part = ( ( extraData['startTask'] - 1 ) % extraData['parts'] ) + 1
            startY = startBox[1] + (part - 1) * self.resY / extraData['parts']
        extraData['totalTasks'] = self.resY / self.verificationOptions.boxSize[1]
        extraData['parts'] = extraData['totalTasks']
        extraData['startTask'] = startY / self.verificationOptions.boxSize[1]  + 1
        extraData['endTask'] = (startY + self.verificationOptions.boxSize[1] ) / self.verificationOptions.boxSize[1]  + 1
        extraData['overlap'] = (( extraData['endTask'] - extraData['startTask']) * self.verificationOptions.boxSize[1])
        if extraData['startTask'] != 1:
            newStartY = extraData['overlap']
        else:
            newStartY = 0
        newStartY += startY % self.verificationOptions.boxSize[1]
        return extraData, (startBox[0], newStartY)

    def __getFrameNumFromOutputFile( self, file_ ):
        fileName = os.path.basename( file_ )
        fileName, ext = os.path.splitext( fileName )
        idx = fileName.find( self.outfilebasename )
        return int( fileName[ idx + len( self.outfilebasename ):] )