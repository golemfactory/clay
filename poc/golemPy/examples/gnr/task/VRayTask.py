import logging
import os
import random
import math
import shutil

from collections import OrderedDict

from TaskState import RendererDefaults, RendererInfo
from GNRTask import GNROptions
from RenderingTask import RenderingTask
from FrameRenderingTask import FrameRenderingTask, FrameRenderingTaskBuiler, getTaskBoarder, getTaskNumFromPixels
from RenderingDirManager import getTestTaskPath, getTmpPath

from RenderingTaskCollector import exr_to_pil, RenderingTaskCollector
from examples.gnr.RenderingEnvironment import VRayEnvironment
from examples.gnr.ui.VRayDialog import VRayDialog
from examples.gnr.customizers.VRayDialogCustomizer import VRayDialogCustomizer
from golem.task.TaskState import SubtaskStatus

logger = logging.getLogger(__name__)

##############################################
def buildVRayRendererInfo():
    defaults = RendererDefaults()
    defaults.outputFormat = "EXR"
    defaults.mainProgramFile = os.path.normpath( os.path.join( os.environ.get('GOLEM'), 'examples\\tasks\\VRayTask.py' ) )
    defaults.minSubtasks = 1
    defaults.maxSubtasks = 100
    defaults.defaultSubtasks = 6

    renderer = RendererInfo( "VRay", defaults, VRayTaskBuilder, VRayDialog, VRayDialogCustomizer, VRayRendererOptions )
    renderer.outputFormats = [ "BMP", "EPS", "EXR", "GIF", "IM", "JPEG", "PCX", "PDF", "PNG", "PPM", "TIFF" ]
    renderer.sceneFileExt = [ "vrscene" ]
    renderer.getTaskNumFromPixels = getTaskNumFromPixels
    renderer.getTaskBoarder = getTaskBoarder

    return renderer

##############################################
class VRayRendererOptions( GNROptions ):

    #######################
    def __init__( self ):
        self.environment = VRayEnvironment()
        self.rtEngine = 0
        self.rtEngineValues = {0: 'No engine', 1: 'CPU', 3: 'OpenGL', 5: 'CUDA' }
        self.useFrames = False
        self.frames = range(1, 11)

##############################################
class VRayTaskBuilder( FrameRenderingTaskBuiler ):
    #######################
    def build( self ):
        mainSceneDir = os.path.dirname( self.taskDefinition.mainSceneFile )

        vRayTask = VRayTask(       self.clientId,
                                   self.taskDefinition.taskId,
                                   mainSceneDir,
                                   self.taskDefinition.mainSceneFile,
                                   self.taskDefinition.mainProgramFile,
                                   self._calculateTotal( buildVRayRendererInfo(), self.taskDefinition ),
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
                                   self.taskDefinition.rendererOptions.rtEngine,
                                   self.taskDefinition.rendererOptions.useFrames,
                                   self.taskDefinition.rendererOptions.frames
                                   )
        return vRayTask

##############################################
class VRayTask( FrameRenderingTask ):
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
                  rtEngine,
                  useFrames,
                  frames,
                  returnAddress = "",
                  returnPort = 0):

        FrameRenderingTask.__init__( self, clientId, taskId, returnAddress, returnPort,
                          VRayEnvironment.getId(), fullTaskTimeout, subtaskTimeout,
                          mainProgramFile, taskResources, mainSceneDir, mainSceneFile,
                          totalTasks, resX, resY, outfilebasename, outputFile, outputFormat,
                          rootPath, estimatedMemory, useFrames, frames )

        self.rtEngine = rtEngine
        self.collectedAlphaFiles = {}

        self.framesParts = {}
        self.framesAlphaParts = {}


    #######################
    def queryExtraData( self, perfIndex, numCores = 0 ):

        startTask, endTask = self._getNextTask()

        workingDirectory = self._getWorkingDirectory()
        sceneFile = self._getSceneFileRelPath()

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
                                    "rtEngine": self.rtEngine,
                                    "useFrames": self.useFrames,
                                    "frames": frames,
                                    "parts": parts
                                }


        hash = "{}".format( random.getrandbits(128) )
        self.subTasksGiven[ hash ] = extraData
        self.subTasksGiven[ hash ][ 'status' ] = SubtaskStatus.starting
        for frame in frames:
            if self.useFrames and frame not in self.framesParts:
                self.framesParts[ frame ] = {}
                self.framesAlphaParts[ frame ] = {}

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

        extraData =          {      "pathRoot" : self.mainSceneDir,
                                    "startTask" : 0,
                                    "endTask" : 1,
                                    "totalTasks" : self.totalTasks,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFile" : sceneFile,
                                    "width" : 1,
                                    "height": 1,
                                    "rtEngine": self.rtEngine,
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

        if not self.shouldAccept( subtaskId ):
            return

        tmpDir = dirManager.getTaskTemporaryDir( self.header.taskId, create = False )

        if len( taskResult ) > 0:
            numStart = self.subTasksGiven[ subtaskId ][ 'startTask' ]
            parts = self.subTasksGiven[ subtaskId ][ 'parts' ]
            numEnd = self.subTasksGiven[ subtaskId ][ 'endTask' ]
            self.subTasksGiven[ subtaskId ][ 'status' ] = SubtaskStatus.finished

            if self.useFrames and self.totalTasks <= len( self.frames ):
                if len( taskResult ) < len( self.subTasksGiven[ subtaskId ][ 'frames' ] ):
                    self._markSubtaskFailed( subtaskId )
                    return

            trFiles = []
            for trp in taskResult:
                trFiles.append( self._unpackTaskResult( trp, tmpDir ) )

            if not self.__verifyImgs( trFiles ):
                self._markSubtaskFailed( subtaskId )
                if not self.useFrames:
                    self._updateTaskPreview()
                else:
                    self._updateFrameTaskPreview()
                return


            if not self.useFrames:
                for trFile in trFiles:
                    self.__collectImagePart( numStart, trFile )
            elif self.totalTasks < len( self.frames ):
                for trFile in trFiles:
                    self.__collectFrameFile( trFile )
                self.__collectFrames( self.subTasksGiven[ subtaskId ][ 'frames' ], tmpDir )
            else:
                for trFile in trFiles:
                    self.__collectFramePart( numStart, trFile, parts, tmpDir )

            self.numTasksReceived += numEnd - numStart + 1
        else:
            self._markSubtaskFailed( subtaskId )
            if not self.useFrames:
                self._updateTaskPreview()
            else:
                self._updateFrameTaskPreview()

        if self.numTasksReceived == self.totalTasks:
            if self.useFrames:
                self.__copyFrames()
            else:
                outputFileName = u"{}".format( self.outputFile, self.outputFormat )
                self.__putImageTogether( outputFileName )

    #######################
    def __useOuterTaskCollector( self ):
        unsupportedFormats = ['EXR', 'EPS']
        if self.outputFormat in unsupportedFormats:
            return True
        return False

    #######################
    def __useAlpha( self ):
        unsupportedFormats = ['BMP', 'PCX', 'PDF']
        if self.outputFormat in unsupportedFormats:
            return False
        return True

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
    def __isAlphaFile(self, fileName ):
        return fileName.find('Alpha') != -1

    #######################
    def __putImageTogether( self, outputFileName  ):
        collector = RenderingTaskCollector()

        if not self.__useOuterTaskCollector():
            for file in self.collectedFileNames.values():
                collector.acceptTask( file )
            for file in self.collectedAlphaFiles.values():
                collector.acceptAlpha( file )
            collector.finalize().save( outputFileName, self.outputFormat )
#            if not self.useFrames:
#                self.previewFilePath = outputFileName
        else:
            self.collectedFileNames = OrderedDict( sorted( self.collectedFileNames.items() ) )
            self.collectedAlphaFiles = OrderedDict( sorted( self.collectedAlphaFiles.items() ) )
            files = " ".join( self.collectedFileNames.values() + self.collectedAlphaFiles.values() )
            self._putCollectedFilesTogether( outputFileName, files, "add" )

    #######################
    def __collectImagePart( self, numStart, trFile ):
        if self.__isAlphaFile( trFile ):
            self.collectedAlphaFiles[ numStart ] = trFile
        else:
            self.collectedFileNames[ numStart ] = trFile
            self._updatePreview( trFile )
            self._updateTaskPreview()

    #######################
    def __collectFrames(self, frames, tmpDir):
        for frame in frames:
            self.__putFrameTogether( tmpDir, frame, frame )


    #######################
    def __collectFrameFile( self, trFile ):
        frameNum = self.__getFrameNumberFromName( trFile )
        if frameNum is None:
            return
        if self.__isAlphaFile( trFile ):
            self.framesAlphaParts[ frameNum ][1] = trFile
        else:
            self.framesParts[ frameNum ][1] = trFile

    #######################
    def __collectFramePart( self, numStart, trFile, parts, tmpDir ):
        frameNum = self.frames[(numStart - 1 ) / parts ]
        part = ( ( numStart - 1 ) % parts ) + 1

        if self.__isAlphaFile( trFile ):
            self.framesAlphaParts[ frameNum ][ part ] = trFile
        else:
            self.framesParts[ frameNum ][ part ] = trFile

        if len( self.framesParts[ frameNum ] ) == parts:
            self.__putFrameTogether( tmpDir, frameNum, numStart )

    #######################
    def __copyFrames( self ):
        outpuDir = os.path.dirname( self.outputFile )
        for file in self.collectedFileNames.values():
            shutil.copy( file, os.path.join( outpuDir, os.path.basename( file ) ) )

    #######################
    def __putFrameTogether( self, tmpDir, frameNum, numStart ):
        outputFileName = os.path.join( tmpDir, self.__getOutputName( frameNum ) )
        if self.__useOuterTaskCollector():
            collected = self.framesParts[ frameNum ]
            collected = OrderedDict( sorted( collected.items() ) )
            collectedAlphas = self.framesAlphaParts[ frameNum ]
            collectedAlphas = OrderedDict( sorted( collectedAlphas.items() ) )
            files = " ".join( collected.values() + collectedAlphas.values() )
            self._putCollectedFilesTogether( outputFileName, files, "add" )
        else:
            collector = RenderingTaskCollector()
            for part in self.framesParts[ frameNum ].values():
                collector.acceptTask( part )
            for part in self.framesAlphaParts[ frameNum ].values():
                collector.acceptAlpha( part )
            collector.finalize().save( outputFileName, self.outputFormat )
        self.collectedFileNames[ numStart ] = outputFileName
        self._updateFramePreview( outputFileName, frameNum )

    #######################
    def __getFrameNumberFromName( self, frameName ):
        frameName, ext = os.path.splitext( frameName )
        try:
            num = int( frameName.split(".")[-1].lstrip("0") )
            return num
        except Exception, err:
            logger.warning("Wrong result name: {}; {} ", frameName, str( err ) )
            return None


    #######################
    def __getOutputName( self, frameNum ):
        num = str( frameNum )
        return "{}{}.{}".format( self.outfilebasename, num.zfill( 4 ), self.outputFormat )

    #######################
    def __verifyImgs( self, trFiles ):
        for trFile in trFiles:
            if not self._verifyImg( trFile, self.resX, self.resY ):
                return False
        return True

