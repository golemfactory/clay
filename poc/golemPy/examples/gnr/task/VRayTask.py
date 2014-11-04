import logging
import os
import random
import pickle
import subprocess

from TaskState import RendererDefaults, RendererInfo
from GNRTask import GNRTaskBuilder, GNRTask, GNROptions
from GNREnv import GNREnv

from examples.gnr.RenderingEnvironment import VRayEnvironment
from examples.gnr.ui.VRayDialog import VRayDialog
from examples.gnr.customizers.VRayDialogCustomizer import VRayDialogCustomizer

from golem.task.TaskBase import ComputeTaskDef
from golem.core.Compress import decompress

from testtasks.pbrt.takscollector import PbrtTaksCollector, exr_to_pil
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

class VRayTaskBuilder( GNRTaskBuilder ):
    def build( self ):
        mainSceneDir = os.path.dirname( self.taskDefinition.mainSceneFile )

        mentalRayTask = VRayTask(self.clientId,
                                   self.taskDefinition,
                                   mainSceneDir,
                                   self.__calculateTotal( self.taskDefinition ),
                                   32,
                                   4,
                                   "temp",
                                   self.rootPath
                                   )
        return mentalRayTask

    def __calculateTotal(self, definition ):
        renderer = buildVRayRendererInfo()

        if definition.optimizeTotal:
            return renderer.defaults.defaultSubtasks

        if renderer.defaults.minSubtasks <= definition.totalSubtasks <= renderer.defaults.maxSubtasks:
            return definition.totalSubtasks
        else :
            return renderer.defaults.defaultSubtasks

class VRayTask( GNRTask ):
    def __init__( self, clientId, taskDefinition, mainSceneDir, totalTasks, numSubtasks, numCores,
                  outfilebasename, rootPath, returnAddress = "", returnPort = 0):

        self.taskDefinition = taskDefinition

        srcFile = open( self.taskDefinition.mainProgramFile, "r")
        srcCode = srcFile.read()

        resourceSize = 0
        for resource in self.taskDefinition.resources:
            resourceSize += os.stat( resource ).st_size

        GNRTask.__init__( self,
                          srcCode,
                          clientId,
                          self.taskDefinition.taskId,
                          returnAddress,
                          returnPort,
                          VRayEnvironment.getId(),
                          self.taskDefinition.fullTaskTimeout,
                          self.taskDefinition.subtaskTimeout,
                          resourceSize )


        self.taskResources = self.taskDefinition.resources
        self.estimatedMemory = self.taskDefinition.estimatedMemory
        self.outputFormat = self.taskDefinition.outputFormat
        self.outputFile = self.taskDefinition.outputFile
        self.mainSceneDir = mainSceneDir
        self.mainProgramFile = self.taskDefinition.mainProgramFile
        self.outfilebasename = outfilebasename

        self.rootPath = rootPath
        self.numCores = numCores
        self.totalTasks = totalTasks
        self.lastTask = 0
        self.numFailedSubtasks = 0
        self.failedSubtasks     = set()
        self.numSubtasks = numSubtasks
        self.sceneFileSrc = ""
        self.previewFilePath    = None

        self.collector          = PbrtTaksCollector()
        self.collectedFileNames = {}
        self.subTasksGiven      = {}
        self.numTasksReceived = 0

        self.fullTaskTimeout = self.taskDefinition.fullTaskTimeout

        self.tmpCnt = 0
        self.collector = PbrtTaksCollector()


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

        if numCores == 0:
            numCores = self.numCores

        commonPathPrefix = os.path.commonprefix( self.taskResources )
        commonPathPrefix = os.path.dirname( commonPathPrefix )

        workingDirectory    = os.path.relpath( self.mainProgramFile, commonPathPrefix )
        workingDirectory    = os.path.dirname( workingDirectory )

        sceneFile = os.path.relpath( os.path.dirname(self.taskDefinition.mainSceneFile), os.path.dirname( self.mainProgramFile ) )
        sceneFile = os.path.join( sceneFile, self.taskDefinition.mainSceneFile )


        extraData =          {      "pathRoot" : self.mainSceneDir,
                                    "startTask" : startTask,
                                    "endTask" : endTask,
                                    "totalTasks" : self.totalTasks,
                                    "numSubtasks" : self.numSubtasks,
                                    "numCores" : numCores,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFile" : sceneFile,
                                    "width" : self.taskDefinition.resolution[0],
                                    "height": self.taskDefinition.resolution[1]
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

        sceneFile = os.path.relpath( os.path.dirname(self.taskDefinition.mainSceneFile), os.path.dirname( self.mainProgramFile ) )
        sceneFile = os.path.join( sceneFile, self.taskDefinition.mainSceneFile )

        extraData =          {      "pathRoot" : self.mainSceneDir,
                                    "startTask" : 0,
                                    "endTask" : 1,
                                    "totalTasks" : self.totalTasks,
                                    "numSubtasks" : self.numSubtasks,
                                    "numCores" : self.numCores,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFile" : sceneFile,
                                    "width" : 1,
                                    "height": 1
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

        self.testTaskResPath = GNREnv.getTestTaskPath( self.rootPath )
        logger.debug( self.testTaskResPath )
        if not os.path.exists( self.testTaskResPath ):
            os.makedirs( self.testTaskResPath )

        ctd.workingDirectory    = workingDirectory

        return ctd

     #######################
    def __shortExtraDataRepr( self, perfIndex, extraData ):
        l = extraData
        return "pathRoot: {}, startTask: {}, endTask: {}, totalTasks: {}, numSubtasks: {}, numCores: {}, outfilebasename: {}, sceneFile: {}".format( l["pathRoot"], l["startTask"], l["endTask"], l["totalTasks"], l["numSubtasks"], l["numCores"], l["outfilebasename"], l["sceneFile"] )

  #######################
    def computationFinished( self, subtaskId, taskResult, dirManager = None ):

        tmpDir = dirManager.getTaskTemporaryDir( self.header.taskId, create = False )

        if len( taskResult ) > 0:
            numStart = self.subTasksGiven[ subtaskId ][ 'startTask' ]
            numEnd = self.subTasksGiven[ subtaskId ][ 'endTask' ]
            for trp in taskResult:
                tr = pickle.loads( trp )
                fh = open( os.path.join( tmpDir, tr[ 0 ] ), "wb" )
                fh.write( decompress( tr[ 1 ] ) )
                fh.close()
                if self.outputFormat != "EXR":
                    self.collector.acceptTask( os.path.join( tmpDir, tr[ 0 ] ) )
                else:
                    self.collectedFileNames[ numStart ] = os.path.join(tmpDir, tr[0] )
                self.__updatePreview( os.path.join( tmpDir, tr[ 0 ] ), numStart )

            self.numTasksReceived += numEnd - numStart + 1



        if self.numTasksReceived == self.totalTasks:
            outputFileName = u"{}".format( self.outputFile, self.outputFormat )

            if self.outputFormat != "EXR":
                self.collector.finalize().save( outputFileName, self.outputFormat )
                self.previewFilePath = outputFileName
            else:
                pth, filename =  os.path.split(os.path.realpath(__file__))
                taskCollectorPath = os.path.join(pth, "..\..\..\\tools\\taskcollector\Release\\taskcollector.exe")
                logger.debug( "taskCollector path: {}".format( taskCollectorPath ) )

                self.collectedFileNames = OrderedDict( sorted( self.collectedFileNames.items() ) )
                files = " ".join( self.collectedFileNames.values() )
                cmd = u"{} add {} {}".format(taskCollectorPath, outputFileName, files )
                logger.debug("cmd = {}".format( cmd ) )
                pc = subprocess.Popen( cmd )
                pc.wait()


   #######################
    def __updatePreview( self, newChunkFilePath, chunkNum ):
        if newChunkFilePath.endswith(".exr"):
            img = exr_to_pil( newChunkFilePath )
        else:
            img = Image.open( newChunkFilePath )

        tmpDir = GNREnv.getTmpPath( self.header.clientId, self.header.taskId, self.rootPath )

        self.previewFilePath = "{}".format( os.path.join( tmpDir, "current_preview") )

        if os.path.exists( self.previewFilePath ):
            imgCurrent = Image.open( self.previewFilePath )
            imgCurrent = ImageChops.add( imgCurrent, img )
            imgCurrent.save( self.previewFilePath, "BMP" )
        else:
            img.save( self.previewFilePath, "BMP" )
