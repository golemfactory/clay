import logging
import os
import random
import pickle
import subprocess

from TaskState import RendererDefaults, RendererInfo
from GNRTask import GNROptions
from RenderingDirManager import getTestTaskPath, getTmpPath
from RenderingTask import RenderingTask, RenderingTaskBuilder
from RenderingTaskCollector import RenderingTaskCollector, exr_to_pil

from examples.gnr.RenderingEnvironment import VRayEnvironment
from examples.gnr.ui.VRayDialog import VRayDialog
from examples.gnr.customizers.VRayDialogCustomizer import VRayDialogCustomizer

from golem.task.TaskBase import ComputeTaskDef
from golem.core.Compress import decompress

from PIL import Image, ImageChops
from collections import OrderedDict

logger = logging.getLogger(__name__)

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

    return renderer


class VRayRendererOptions( GNROptions ):
    def __init__( self ):
        self.environment = VRayEnvironment()
        self.rtEngine = 0
        self.rtEngineValues = {0: 'No engine', 1: 'CPU', 3: 'OpenGL', 5: 'CUDA' }

class VRayTaskBuilder( RenderingTaskBuilder ):
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
                                   "temp",
                                   self.taskDefinition.outputFile,
                                   self.taskDefinition.outputFormat,
                                   self.taskDefinition.fullTaskTimeout,
                                   self.taskDefinition.subtaskTimeout,
                                   self.taskDefinition.resources,
                                   self.taskDefinition.estimatedMemory,
                                   self.rootPath,
                                   self.taskDefinition.rendererOptions.rtEngine
                                   )
        return vRayTask

class VRayTask( RenderingTask ):
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
                  returnAddress = "",
                  returnPort = 0):

        RenderingTask.__init__( self, clientId, taskId, returnAddress, returnPort,
                          VRayEnvironment.getId(), fullTaskTimeout, subtaskTimeout,
                          mainProgramFile, taskResources, mainSceneDir, mainSceneFile,
                          totalTasks, resX, resY, outfilebasename, outputFile, outputFormat,
                          rootPath, estimatedMemory )

        self.rtEngine = rtEngine
        self.collectedAlphaFiles = {}


    #######################
    def queryExtraData( self, perfIndex, numCores = 0 ):

        if self.lastTask != self.totalTasks:
            self.lastTask += 1
            startTask = self.lastTask
            endTask = self.lastTask
        else:
            subtask = self.failedSubtasks.pop()
            self.numFailedSubtasks -= 1
            endTask = subtask.endChunk
            startTask = subtask.startChunk

        commonPathPrefix = os.path.commonprefix( self.taskResources )
        commonPathPrefix = os.path.dirname( commonPathPrefix )

        workingDirectory    = os.path.relpath( self.mainProgramFile, commonPathPrefix )
        workingDirectory    = os.path.dirname( workingDirectory )

        sceneFile = os.path.relpath( os.path.dirname(self.mainSceneFile), os.path.dirname( self.mainProgramFile ) )
        sceneFile = os.path.join( sceneFile, os.path.basename( self.mainSceneFile ) )

        extraData =          {      "pathRoot" : self.mainSceneDir,
                                    "startTask" : startTask,
                                    "endTask" : endTask,
                                    "totalTasks" : self.totalTasks,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFile" : sceneFile,
                                    "width" : self.resX,
                                    "height": self.resY,
                                    "rtEngine": self.rtEngine
                                }



        hash = "{}".format( random.getrandbits(128) )
        self.subTasksGiven[ hash ] = extraData

        ctd = ComputeTaskDef()
        ctd.taskId              = self.header.taskId
        ctd.subtaskId           = hash
        ctd.extraData           = extraData
        ctd.returnAddress       = self.header.taskOwnerAddress
        ctd.returnPort          = self.header.taskOwnerPort
        ctd.shortDescription    = self.__shortExtraDataRepr( perfIndex, extraData )
        ctd.srcCode             = self.srcCode
        ctd.performance         = perfIndex

        ctd.workingDirectory    = workingDirectory

        logger.debug( ctd.workingDirectory )

        return ctd

    #######################
    def queryExtraDataForTestTask( self ):

        commonPathPrefix = os.path.commonprefix( self.taskResources )
        commonPathPrefix = os.path.dirname( commonPathPrefix )

        workingDirectory    = os.path.relpath( self.mainProgramFile, commonPathPrefix )
        workingDirectory    = os.path.dirname( workingDirectory )

        sceneFile = os.path.relpath( os.path.dirname(self.mainSceneFile), os.path.dirname( self.mainProgramFile ) )
        sceneFile = os.path.join( sceneFile, self.mainSceneFile )

        extraData =          {      "pathRoot" : self.mainSceneDir,
                                    "startTask" : 0,
                                    "endTask" : 1,
                                    "totalTasks" : self.totalTasks,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFile" : sceneFile,
                                    "width" : 1,
                                    "height": 1,
                                    "rtEngine": self.rtEngine
                                }

        hash = "{}".format( random.getrandbits(128) )

        ctd = ComputeTaskDef()
        ctd.taskId              = self.header.taskId
        ctd.subtaskId           = hash
        ctd.extraData           = extraData
        ctd.returnAddress       = self.header.taskOwnerAddress
        ctd.returnPort          = self.header.taskOwnerPort
        ctd.shortDescription    = self.__shortExtraDataRepr( 0, extraData )
        ctd.srcCode             = self.srcCode
        ctd.performance         = 0

        self.testTaskResPath = getTestTaskPath( self.rootPath )
        logger.debug( self.testTaskResPath )
        if not os.path.exists( self.testTaskResPath ):
            os.makedirs( self.testTaskResPath )

        ctd.workingDirectory    = workingDirectory

        return ctd

     #######################
    def __shortExtraDataRepr( self, perfIndex, extraData ):
        l = extraData
        return "pathRoot: {}, startTask: {}, endTask: {}, totalTasks: {}, outfilebasename: {}, sceneFile: {}".format( l["pathRoot"], l["startTask"], l["endTask"], l["totalTasks"], l["outfilebasename"], l["sceneFile"] )

  #######################
    def computationFinished( self, subtaskId, taskResult, dirManager = None ):

        tmpDir = dirManager.getTaskTemporaryDir( self.header.taskId, create = False )

        if len( taskResult ) > 0:
            numStart = self.subTasksGiven[ subtaskId ][ 'startTask' ]
            numEnd = self.subTasksGiven[ subtaskId ][ 'endTask' ]
            for trp in taskResult:
                trFile = self._unpackTaskResult( trp, tmpDir )
                if self.outputFormat != "EXR" and self.outputFormat != "TIFF":
                    self.collector.acceptTask( trFile )
                else:
                    if trFile.find('Alpha') != -1:
                        self.collectedAlphaFiles[ numStart ] = trFile
                    else:
                        self.collectedFileNames[ numStart ] = trFile
                        self._updatePreview( trFile )

            self.numTasksReceived += numEnd - numStart + 1

        if self.numTasksReceived == self.totalTasks:
            outputFileName = u"{}".format( self.outputFile, self.outputFormat )

            if self.outputFormat != "EXR" and self.outputFormat != "TIFF":
                self.collector.finalize().save( outputFileName, self.outputFormat )
                self.previewFilePath = outputFileName
            else:
                self.collectedFileNames = OrderedDict( sorted( self.collectedFileNames.items() ) )
                self.collectedAlphaFiles = OrderedDict( sorted( self.collectedAlphaFiles.items() ) )
                files = " ".join( self.collectedFileNames.values() + self.collectedAlphaFiles.values() )
                self._putCollectedFilesTogether( outputFileName, files, "add" )

