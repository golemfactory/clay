import logging
import random
import os
import math

from collections import OrderedDict
from PIL import Image, ImageChops

from golem.task.TaskState import SubtaskStatus

from examples.gnr.RenderingDirManager import getTestTaskPath, getTmpPath
from examples.gnr.RenderingEnvironment import BlenderEnvironment
from examples.gnr.RenderingTaskState import RendererDefaults, RendererInfo

from examples.gnr.task.GNRTask import GNROptions, checkSubtaskIdWrapper
from examples.gnr.task.FrameRenderingTask import FrameRenderingTask, FrameRenderingTaskBuiler, getTaskBoarder, getTaskNumFromPixels
from examples.gnr.task.RenderingTaskCollector import RenderingTaskCollector, exr_to_pil
from examples.gnr.task.SceneFileEditor import regenerateBlenderCropFile

from examples.gnr.ui.BlenderRenderDialog import BlenderRenderDialog
from examples.gnr.customizers.BlenderRenderDialogCustomizer import BlenderRenderDialogCustomizer

logger = logging.getLogger(__name__)

##############################################
def buildBlenderRendererInfo():
    defaults = RendererDefaults()
    defaults.outputFormat = "EXR"
    defaults.mainProgramFile = os.path.normpath( os.path.join( os.environ.get('GOLEM'), 'examples\\tasks\\blenderTask.py' ) )
    defaults.minSubtasks = 1
    defaults.maxSubtasks = 100
    defaults.defaultSubtasks = 6

    renderer = RendererInfo( "Blender", defaults, BlenderRenderTaskBuilder, BlenderRenderDialog, BlenderRenderDialogCustomizer, BlenderRendererOptions )
    renderer.outputFormats = [ "PNG", "TGA", "EXR" ]
    renderer.sceneFileExt = [ "blend" ]
    renderer.getTaskNumFromPixels = getTaskNumFromPixels
    renderer.getTaskBoarder = getTaskBoarder

    return renderer

##############################################
class BlenderRendererOptions( GNROptions ):
    #######################
    def __init__( self ):
        self.environment = BlenderEnvironment()
        self.engineValues = ["BLENDER_RENDER", "BLENDER_GAME", "CYCLES"]
        self.engine = "BLENDER_RENDER"
        self.useFrames = False
        self.frames = range(1, 11)

##############################################
class BlenderRenderTaskBuilder( FrameRenderingTaskBuiler ):
    #######################
    def build( self ):
        mainSceneDir = os.path.dirname( self.taskDefinition.mainSceneFile )

        vRayTask = BlenderRenderTask(       self.clientId,
                                   self.taskDefinition.taskId,
                                   mainSceneDir,
                                   self.taskDefinition.mainSceneFile,
                                   self.taskDefinition.mainProgramFile,
                                   self._calculateTotal( buildBlenderRendererInfo(), self.taskDefinition ),
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
                                   self.taskDefinition.rendererOptions.useFrames,
                                   self.taskDefinition.rendererOptions.frames,
                                   self.taskDefinition.rendererOptions.engine
                                   )
        return self._setVerificationOptions( vRayTask )


##############################################
class BlenderRenderTask( FrameRenderingTask ):
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
                  useFrames,
                  frames,
                  engine,
                  returnAddress = "",
                  returnPort = 0):

        FrameRenderingTask.__init__( self, clientId, taskId, returnAddress, returnPort,
                          BlenderEnvironment.getId(), fullTaskTimeout, subtaskTimeout,
                          mainProgramFile, taskResources, mainSceneDir, mainSceneFile,
                          totalTasks, resX, resY, outfilebasename, outputFile, outputFormat,
                          rootPath, estimatedMemory, useFrames, frames )

        cropTask = os.path.normpath( os.path.join( os.environ.get( 'GOLEM'), 'examples\\tasks\\blenderCrop.py') )
        try:
            with open( cropTask ) as f:
                self.scriptSrc = f.read()
        except Exception, err:
            logger.error( "Wrong script file: {}".format( str( err ) ) )
            self.scriptSrc = ""

        self.engine = engine

        self.framesGiven = {}
        for frame in frames:
            self.framesGiven[ frame ] = {}

    #######################
    def queryExtraData( self, perfIndex, numCores = 0, clientId = None ):

        if not self._acceptClient( clientId ):
            logger.warning(" Client {} banned from this task ".format( clientId ) )
            return None

        startTask, endTask = self._getNextTask()

        workingDirectory = self._getWorkingDirectory()
        sceneFile = self._getSceneFileRelPath()

        if self.useFrames:
            frames, parts = self._chooseFrames( self.frames, startTask, self.totalTasks )
        else:
            frames = [1]
            parts = 1

        if not self.useFrames:
            scriptSrc = regenerateBlenderCropFile( self.scriptSrc, self.resX, self.resY, self.totalTasks, startTask )
        elif parts > 1:
            scriptSrc = regenerateBlenderCropFile( self.scriptSrc, self.resX, self.resY, parts, self._countPart( startTask, parts ) )
        else:
            scriptSrc = regenerateBlenderCropFile( self.scriptSrc, self.resX, self.resY, 1, 1 )

        extraData =          {      "pathRoot": self.mainSceneDir,
                                    "startTask" : startTask,
                                    "endTask": endTask,
                                    "totalTasks": self.totalTasks,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFile" : sceneFile,
                                    "scriptSrc": scriptSrc,
                                    "engine": self.engine,
                                    "frames": frames,
                                }


        hash = "{}".format( random.getrandbits(128) )
        self.subTasksGiven[ hash ] = extraData
        self.subTasksGiven[ hash ][ 'status' ] = SubtaskStatus.starting
        self.subTasksGiven[ hash ][ 'perf' ] = perfIndex
        self.subTasksGiven[ hash ][ 'clientId' ] = clientId
        self.subTasksGiven[ hash ][ 'parts' ] = parts


        if not self.useFrames:
            self._updateTaskPreview()
        else:
            self._updateFrameTaskPreview()

        return self._newComputeTaskDef( hash, extraData, workingDirectory, perfIndex )

    #######################
    def queryExtraDataForTestTask( self ):

        workingDirectory = self._getWorkingDirectory()
        sceneFile = self._getSceneFileRelPath()

        if self.useFrames:
            frames = [ self.frames[0] ]
        else:
            frames = []

        if self.useFrames:
            frames = [ self.frames[0] ]
        else:
            frames = [1]

        scriptSrc = regenerateBlenderCropFile( self.scriptSrc, 5, 5, 1, 1)
        print scriptSrc

        extraData =          {      "pathRoot": self.mainSceneDir,
                                    "startTask" : 1,
                                    "endTask": 1,
                                    "totalTasks": self.totalTasks,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFile" : sceneFile,
                                    "scriptSrc": scriptSrc,
                                    "engine": self.engine,
                                    "frames": frames
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
            numEnd = self.subTasksGiven[ subtaskId ][ 'endTask' ]
            parts = self.subTasksGiven[ subtaskId ][ 'parts' ]
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
    def _getOutputName( self, frameNum, numStart ):
        num = str( frameNum )
        return "{}{}.{}".format( self.outfilebasename, num.zfill(4), self.outputFormat )