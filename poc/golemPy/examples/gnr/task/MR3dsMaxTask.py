import logging
import random
import os
import shutil
import math

from GNRTask import  GNROptions
from RenderingDirManager import getTestTaskPath, getTmpPath
from TaskState import RendererDefaults, RendererInfo

from RenderingTaskCollector import exr_to_pil
from RenderingTask import RenderingTask, RenderingTaskBuilder
from examples.gnr.RenderingEnvironment import ThreeDSMaxEnvironment
from examples.gnr.ui.MentalRayDialog import MentalRayDialog
from examples.gnr.customizers.MentalRayDialogCustomizer import MentalRayDialogCustomizer


from collections import OrderedDict
from PIL import Image, ImageChops


logger = logging.getLogger(__name__)

##############################################
def buildMentalRayRendererInfo():
    defaults = RendererDefaults()
    defaults.outputFormat       = "EXR"
    defaults.mainProgramFile    = os.path.normpath( os.path.join( os.environ.get( 'GOLEM' ), 'examples\\tasks\\3dsMaxTask.py' ) )
    defaults.minSubtasks        = 1
    defaults.maxSubtasks        = 100
    defaults.defaultSubtasks    = 6


    renderer                = RendererInfo( "MentalRay", defaults, MentalRayTaskBuilder, MentalRayDialog, MentalRayDialogCustomizer, MentalRayRendererOptions )
    renderer.outputFormats  = [ "BMP", "EPS", "EXR", "GIF", "IM", "JPEG", "PCD", "PCX", "PNG", "PPM", "PSD", "TIFF", "XBM", "XPM" ]
    renderer.sceneFileExt   = [ "max",  "zip" ]

    return renderer

##############################################
class MentalRayRendererOptions ( GNROptions ):
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
class MentalRayTaskBuilder( RenderingTaskBuilder ):
    #######################
    def build( self ):
        mainSceneDir = os.path.dirname( self.taskDefinition.mainSceneFile )

        mentalRayTask = MentalRayTask(self.clientId,
                                   self.taskDefinition.taskId,
                                   mainSceneDir,
                                   self.taskDefinition.mainSceneFile,
                                   self.taskDefinition.mainProgramFile,
                                   self._calculateTotal( buildMentalRayRendererInfo(), self.taskDefinition ),
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
        return mentalRayTask

    #######################
    def _calculateTotal(self, renderer, definition ):
        if definition.optimizeTotal:
            if self.taskDefinition.rendererOptions.useFrames:
                return len( self.taskDefinition.rendererOptions.frames )
            else:
                return renderer.defaults.defaultSubtasks

        if self.taskDefinition.rendererOptions.useFrames:
            numFrames = len( self.taskDefinition.rendererOptions.frames )
            if definition.totalSubtasks > numFrames:
                est = int( math.floor( float( definition.totalSubtasks ) / float( numFrames ) ) ) * numFrames
                if est != definition.totalSubtasks:
                    logger.warning("Too many subtasks for this task. {} subtasks will be used".format( numFrames ) )
                return est

            est = int ( math.ceil( float( numFrames ) / float( math.ceil( float( numFrames ) / float( definition.totalSubtasks ) ) ) ) )
            if est != definition.totalSubtasks:
                logger.warning("Too many subtasks for this task. {} subtasks will be used.".format( est ) )

            return est

        if renderer.defaults.minSubtasks <= definition.totalSubtasks <= renderer.defaults.maxSubtasks:
            return definition.totalSubtasks
        else :
            return renderer.defaults.defaultSubtasks

##############################################
class MentalRayTask( RenderingTask ):

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

        RenderingTask.__init__( self, clientId, taskId, returnAddress, returnPort,
                          ThreeDSMaxEnvironment.getId(), fullTaskTimeout, subtaskTimeout,
                          mainProgramFile, taskResources, mainSceneDir, mainSceneFile,
                          totalTasks, resX, resY, outfilebasename, outputFile, outputFormat,
                          rootPath, estimatedMemory )


        self.presetFile = presetFile
        self.cmd        = cmdFile
        self.useFrames  = useFrames
        self.frames     = frames
        self.framesGiven = {}

        if useFrames:
            self.previewFilePath = [ None ] * len ( frames )

    #######################
    def restart( self ):
        RenderingTask.restart( self )
        if self.useFrames:
            self.previewFilePath = [ None ] * len( self.frames )

    #######################
    def queryExtraData( self, perfIndex, numCores = 0 ):

        startTask, endTask = self._getNextTask()

        workingDirectory = self._getWorkingDirectory()
        presetFile = self.__getPresetFileRelPath()
        sceneFile = self._getSceneFileRelPath()
        cmdFile = os.path.basename( self.cmd )

        if self.useFrames:
            frames, parts = self.__chooseFrames( self.frames, startTask, self.totalTasks )
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
                                    "useFrames": self.useFrames,
                                    "frames": frames,
                                    "parts": parts
                                }



        hash = "{}".format( random.getrandbits(128) )
        self.subTasksGiven[ hash ] = extraData
        self.subTasksGiven[ hash ]['status' ] = 'sent'
        if parts != 1:
            self.framesGiven[ frames[0] ] = {}
        self._updateTaskPreview()

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
                                    "startTask" : 0,
                                    "endTask" : 1,
                                    "totalTasks" : self.totalTasks,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFile" : sceneFile,
                                    "width" : 1,
                                    "height": 1,
                                    "presetFile": presetFile,
                                    "cmdFile": cmdFile,
                                    "useFrames": self.useFrames,
                                    "frames": frames, 
                                    "parts": 1
                                }

        hash = "{}".format( random.getrandbits(128) )

        self.testTaskResPath = getTestTaskPath( self.rootPath )
        logger.debug( self.testTaskResPath )
        if not os.path.exists( self.testTaskResPath ):
            os.makedirs( self.testTaskResPath )

        return self._newComputeTaskDef( hash, extraData, workingDirectory, 0 )

  #######################
    def computationFinished( self, subtaskId, taskResult, dirManager = None ):

        tmpDir = dirManager.getTaskTemporaryDir( self.header.taskId, create = False )

        if len( taskResult ) > 0:
            numStart = self.subTasksGiven[ subtaskId ][ 'startTask' ]
            parts = self.subTasksGiven[ subtaskId ][ 'parts' ]
            numEnd = self.subTasksGiven[ subtaskId ][ 'endTask' ]
            self.subTasksGiven[ subtaskId ][ 'status' ] = 'finished'

            if self.useFrames and self.totalTasks <= len( self.frames ):
                framesList = self.subTasksGiven[ subtaskId ]['frames']

            for trp in taskResult:
                trFile = self._unpackTaskResult( trp, tmpDir )

                if not self.useFrames:
                    self.__collectImagePart( numStart, trFile )
                elif self.totalTasks <= len( self.frames ):
                    framesList = self.__collectFrames( numStart, trFile, framesList )
                else:
                    self.__collectFramePart( numStart, trFile, parts, tmpDir )

            self.numTasksReceived += numEnd - numStart + 1

        if self.numTasksReceived == self.totalTasks:
            if self.useFrames:
                self.__copyFrames()
            else:
                self.__putImageTogether( tmpDir )

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
    def _updateFramePreview( self, newChunkFilePath, frameNum ):

        num = self.frames.index(frameNum)

        if newChunkFilePath.endswith(".exr"):
            img = exr_to_pil( newChunkFilePath )
        else:
            img = Image.open( newChunkFilePath )

        tmpDir = getTmpPath( self.header.clientId, self.header.taskId, self.rootPath )

        self.previewFilePath[ num ] = "{}{}".format( os.path.join( tmpDir, "current_preview" ), num )
        print self.previewFilePath[num]

        img.save( self.previewFilePath[ num ], "BMP" )

    #######################
    def __chooseFrames( self, frames, startTask, totalTasks ):
        if totalTasks <= len( frames ):
            subtasksFrames = int ( math.ceil( float( len( frames ) ) / float( totalTasks ) ) )
            startFrame = (startTask - 1) * subtasksFrames
            endFrame = min( startTask * subtasksFrames, len( frames ) )
            return frames[ startFrame:endFrame ], 1
        else:
            parts = totalTasks / len( frames )
            return [ frames[(startTask - 1 ) / parts ] ], parts


    #######################
    def __getOutputName( self, frameNum ):
        if frameNum < 10:
            frameNum = "000{}".format( frameNum )
        elif frameNum < 100:
            frameNum = "00{}".format( frameNum )
        elif frameNum < 1000:
            frameNum = "0{}".format( frameNum )
        else:
            frameNum = "{}".format( frameNum )
        return "{}{}.exr".format( self.outfilebasename, frameNum )

    #######################
    def __putFrameTogether( self, tmpDir, frameNum, numStart ):
        outputFileName = os.path.join( tmpDir, self.__getOutputName( frameNum ) )
        collected = self.framesGiven[ frameNum ]
        collected = OrderedDict( sorted( collected.items() ) )
        files = " ".join( collected.values() )
        self._putCollectedFilesTogether( outputFileName, files, "paste" )
        self.collectedFileNames[ numStart ] = outputFileName
        self._updateFramePreview( outputFileName, frameNum )

    #######################
    def __putImageTogether( self, tmpDir ):
        outputFileName = u"{}".format( self.outputFile, self.outputFormat )
        self.collectedFileNames = OrderedDict( sorted( self.collectedFileNames.items() ) )
        files = " ".join( self.collectedFileNames.values() )
        self._putCollectedFilesTogether ( os.path.join( tmpDir, outputFileName ), files, "paste" )

    #######################
    def __copyFrames( self ):
        outpuDir = os.path.dirname( self.outputFile )
        for file in self.collectedFileNames.values():
            shutil.copy( file, os.path.join( outpuDir, os.path.basename( file ) ) )

    #######################
    def __collectImagePart( self, numStart, trFile ):
        self.collectedFileNames[ numStart ] = trFile
        self._updatePreview(trFile, numStart)
        self._updateTaskPreview()

    #######################
    def __collectFrames( self, numStart, trFile, framesList ):
        self.collectedFileNames[ numStart ] = trFile
        self._updateFramePreview( trFile, framesList[0] )
        return framesList[1:]

    #######################
    def __collectFramePart( self, numStart, trFile, parts, tmpDir ):
        frameNum = self.frames[(numStart - 1 ) / parts ]
        part = ( ( numStart - 1 ) % parts ) + 1
        self.framesGiven[ frameNum ][ part ] = trFile

        if len( self.framesGiven[ frameNum ] ) == parts:
            self.__putFrameTogether( tmpDir, frameNum, numStart )

    #######################
    def __getPresetFileRelPath( self ):
        presetFile = os.path.relpath( os.path.dirname( self.presetFile ), os.path.dirname( self.mainProgramFile ) )
        presetFile = os.path.join( presetFile, os.path.basename( self.presetFile ) )
        return presetFile



