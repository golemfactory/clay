import os
import random
import cPickle as pickle
import logging
import time
import subprocess

from golem.task.TaskBase import ComputeTaskDef
from golem.core.Compress import decompress
from golem.resource.Resource import prepareDeltaZip
from examples.gnr.RenderingEnvironment import PBRTEnvironment

from examples.gnr.task.SceneFileEditor import regenerateFile

from GNRTask import GNRTask, GNRSubtask, GNRTaskBuilder
from testtasks.pbrt.takscollector import PbrtTaksCollector, exr_to_pil
from GNREnv import GNREnv

import OpenEXR, Imath
from PIL import Image, ImageChops

logger = logging.getLogger(__name__)

class PbrtRenderOptions:
    def __init__( self ):
        self.pixelFilter = "mitchell"
        self.samplesPerPixelCount = 32
        self.algorithmType = "lowdiscrepancy"
        self.minSubtasks = 4
        self.maxSubtasks = 200
        self.defaultSubtasks = 60

    def addToResources( self , resources ):
        return resources

class PbrtTaskBuilder( GNRTaskBuilder ):
    #######################
    def build( self ):
        mainSceneDir = os.path.dirname( self.taskDefinition.mainSceneFile )

        pbrtTask = PbrtRenderTask( self.clientId,
                                   self.taskDefinition.id,
                                   mainSceneDir,
                                   self.taskDefinition.mainProgramFile,
                                   self.__calculateTotal( self.taskDefinition ),
                                   32,
                                   4,
                                   self.taskDefinition.resolution[ 0 ],
                                   self.taskDefinition.resolution[ 1 ],
                                   self.taskDefinition.rendererOptions.pixelFilter,
                                   self.taskDefinition.rendererOptions.algorithmType,
                                   self.taskDefinition.rendererOptions.samplesPerPixelCount,
                                   "temp",
                                   self.taskDefinition.mainSceneFile,
                                   self.taskDefinition.fullTaskTimeout,
                                   self.taskDefinition.subtaskTimeout,
                                   self.taskDefinition.resources,
                                   self.taskDefinition.outputFile,
                                   self.taskDefinition.outputFormat,
                                   self.taskDefinition.estimatedMemory,
                                   self.rootPath
                                  )

        return pbrtTask
    #######################
    def __calculateTotal( self, definition ):
        options = PbrtRenderOptions()

        if (not definition.optimizeTotal) and (options.minSubtasks <= definition.totalSubtasks <= options.maxSubtasks):
            return definition.totalSubtasks

        taskBase = 1000000
        allOp = definition.resolution[0] * definition.resolution[1] * definition.rendererOptions.samplesPerPixelCount
        return max( options.minSubtasks, min( options.maxSubtasks, allOp / taskBase ) )

class PbrtRenderTask( GNRTask ):

    #######################
    def __init__( self,
                  clientId,
                  taskId,
                  pathRoot,
                  mainProgramFile,
                  totalTasks,
                  numSubtasks,
                  numCores,
                  resX,
                  resY,
                  pixelFilter,
                  sampler,
                  samplesPerPixel,
                  outfilebasename,
                  sceneFile,
                  fullTaskTimeout,
                  subtaskTimeout,
                  taskResources,
                  outputFile,
                  outputFormat,
                  estimatedMemory,
                  rootPath,
                  returnAddress = "",
                  returnPort = 0
                  ):

        srcFile = open( mainProgramFile, "r")
        srcCode = srcFile.read()

        resourceSize = 0
        for resource in taskResources:
            resourceSize += os.stat(resource).st_size

        GNRTask.__init__( self, srcCode, clientId, taskId, returnAddress, returnPort, PBRTEnvironment.getId(), fullTaskTimeout, subtaskTimeout, resourceSize )

        self.fullTaskTimeout = max( 2200.0, fullTaskTimeout )
        self.header.ttl = self.fullTaskTimeout
        self.header.subtaskTimeout = max( 220.0, subtaskTimeout )


        self.pathRoot           = pathRoot
        self.lastTask           = 0
        self.totalTasks         = totalTasks
        self.numSubtasks        = numSubtasks
        self.numCores           = numCores
        self.outfilebasename    = outfilebasename
        self.sceneFileSrc       = open(sceneFile).read()
        self.taskResources      = taskResources
        self.resourceSize       = resourceSize
        self.mainProgramFile    = mainProgramFile
        self.outputFile         = outputFile
        self.outputFormat       = outputFormat
        self.resX               = resX
        self.resY               = resY
        self.pixelFilter        = pixelFilter
        self.sampler            = sampler
        self.samplesPerPixel    = samplesPerPixel
        self.estimatedMemory    = estimatedMemory

        self.numFailedSubtasks  = 0
        self.failedSubtasks     = set()

        self.collector          = PbrtTaksCollector()
        self.collectedFileNames = []
        self.numTasksReceived   = 0
        self.subTasksGiven      = {}

        self.previewFilePath    = None
        self.rootPath           = rootPath


    #######################
    def queryExtraData( self, perfIndex, numCores = 0 ):

        if ( self.lastTask != self.totalTasks ):
            perf = max( int( float( perfIndex ) / 1500 ), 1)
            endTask = min( self.lastTask + perf, self.totalTasks )
            startTask = self.lastTask
            self.lastTask = endTask
        else:
            subtask = self.failedSubtasks.pop()
            self.numFailedSubtasks -= 1
            endTask = subtask.endChunk
            startTask = subtask.startChunk

        if numCores == 0:
            numCores = self.numCores

        commonPathPrefix = os.path.commonprefix( self.taskResources )
        commonPathPrefix = os.path.dirname( commonPathPrefix )

        sceneSrc = regenerateFile( self.sceneFileSrc, self.resX, self.resY, self.pixelFilter, self.sampler, self.samplesPerPixel )

        extraData =          {      "pathRoot" : self.pathRoot,
                                    "startTask" : startTask,
                                    "endTask" : endTask,
                                    "totalTasks" : self.totalTasks,
                                    "numSubtasks" : self.numSubtasks,
                                    "numCores" : numCores,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFileSrc" : sceneSrc
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

        ctd.workingDirectory    = os.path.relpath( self.mainProgramFile, commonPathPrefix )
        ctd.workingDirectory    = os.path.dirname( ctd.workingDirectory )

        logger.debug(ctd.workingDirectory)

        # ctd.workingDirectory = ""


        return ctd


    #######################
    def queryExtraDataForTestTask( self ):

        sceneSrc = regenerateFile( self.sceneFileSrc, 1, 1, self.pixelFilter, self.sampler, self.samplesPerPixel )

        extraData =          {      "pathRoot" : self.pathRoot,
                                    "startTask" : 0,
                                    "endTask" : 1,
                                    "totalTasks" : self.totalTasks,
                                    "numSubtasks" : self.numSubtasks,
                                    "numCores" : self.numCores,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFileSrc" : sceneSrc
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

        ctd.workingDirectory    = os.path.relpath( self.mainProgramFile, self.testTaskResPath)
        ctd.workingDirectory    = os.path.dirname( ctd.workingDirectory )

        return ctd

    #######################
    def __shortExtraDataRepr( self, perfIndex, extraData ):
        l = extraData
        return "pathRoot: {}, startTask: {}, endTask: {}, totalTasks: {}, numSubtasks: {}, numCores: {}, outfilebasename: {}, sceneFileSrc: {}".format( l["pathRoot"], l["startTask"], l["endTask"], l["totalTasks"], l["numSubtasks"], l["numCores"], l["outfilebasename"], l["sceneFileSrc"] )

    #######################
    def computationFinished( self, subtaskId, taskResult, env = None ):

        tmpDir = env.getTaskTemporaryDir( self.header.taskId )

        if len( taskResult ) > 0:
            for trp in taskResult:
                tr = pickle.loads( trp )
                fh = open( os.path.join( tmpDir, tr[ 0 ] ), "wb" )
                fh.write( decompress( tr[ 1 ] ) )
                fh.close()

                if (self.outputFormat != "EXR"):
                    self.collector.acceptTask( os.path.join( tmpDir, tr[ 0 ] ) ) # pewnie tutaj trzeba czytac nie zpliku tylko z streama
                else:
                    self.collectedFileNames.append( os.path.join(tmpDir, tr[0] ) )
                self.numTasksReceived += 1

                self.__updatePreview( os.path.join( tmpDir, tr[ 0 ] ) )

        if self.numTasksReceived == self.totalTasks:
            outputFileName = u"{}".format( self.outputFile, self.outputFormat )
            if (self.outputFormat != "EXR"):
                self.collector.finalize().save( outputFileName, self.outputFormat )
                self.previewFilePath = outputFileName
            else:

                pth, filename =  os.path.split(os.path.realpath(__file__))
                taskCollectorPath = os.path.join(pth, "..\..\..\\tools\\taskcollector\Release\\taskcollector.exe")
                logger.debug( "taskCollector path: {}".format( taskCollectorPath ) )
                files = ""
                for file in self.collectedFileNames:
                    files += file + " "
                cmd = u"{} pbrt {} {}".format(taskCollectorPath, outputFileName, files )
                pc = subprocess.Popen( cmd )
                pc.wait()

    #######################
    def __updatePreview( self, newChunkFilePath ):

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
