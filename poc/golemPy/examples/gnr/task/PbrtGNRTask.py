import os
import random
import cPickle as pickle
import logging

from golem.task.TaskBase import TaskBuilder, ComputeTaskDef
from golem.task.TaskState import TaskStatus
from golem.core.Compress import decompress
from golem.task.resource.Resource import prepareDeltaZip

from examples.gnr.task.SceneFileEditor import regenerateFile

from GNRTask import GNRTask
from testtasks.pbrt.takscollector import PbrtTaksCollector
from GNREnv import GNREnv

import OpenEXR, Imath
from PIL import Image, ImageChops

class PbrtTaskBuilder( TaskBuilder ):
    #######################
    def __init__( self, clientId, taskDefinition, env ):
        self.taskDefinition = taskDefinition
        self.clientId       = clientId
        self.env = env

    #######################
    def build( self ):
        mainSceneDir = os.path.dirname( self.taskDefinition.mainSceneFile )

        # TODO: Calculate total task

        pbrtTask = PbrtRenderTask( self.clientId,
                                   self.taskDefinition.id,
                                   mainSceneDir,
                                   self.taskDefinition.mainProgramFile,
                                   100,
                                   32,
                                   4,
                                   self.taskDefinition.resolution[ 0 ],
                                   self.taskDefinition.resolution[ 1 ],
                                   self.taskDefinition.pixelFilter,
                                   self.taskDefinition.algorithmType,
                                   self.taskDefinition.samplesPerPixelCount,
                                   "temp",
                                   self.taskDefinition.mainSceneFile,
                                   self.taskDefinition.fullTaskTimeout,
                                   self.taskDefinition.resources,
                                   self.taskDefinition.outputFile,
                                   self.taskDefinition.outputFormat,
                                   self.env
                                  )

        return pbrtTask


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
                  taskResources,
                  outputFile,
                  outputFormat,
                  env,
                  returnAddress = "",
                  returnPort = 0
                  ):

        srcFile = open( mainProgramFile, "r")
        srcCode = srcFile.read()

        GNRTask.__init__( self, srcCode, clientId, taskId, returnAddress, returnPort, fullTaskTimeout )

        self.header.ttl = max( 2200.0, fullTaskTimeout )

        self.pathRoot           = pathRoot
        self.lastTask           = 0
        self.totalTasks         = totalTasks
        self.numSubtasks        = numSubtasks
        self.numCores           = numCores
        self.outfilebasename    = outfilebasename
        self.sceneFileSrc       = open(sceneFile).read()
        self.taskResources      = taskResources
        self.mainProgramFile    = mainProgramFile
        self.outputFile         = outputFile
        self.outputFormat       = outputFormat
        self.resX               = resX
        self.resY               = resY
        self.pixelFilter        = pixelFilter
        self.sampler            = sampler
        self.samplesPerPixel    = samplesPerPixel

        self.collector          = PbrtTaksCollector()
        self.numTasksReceived   = 0
        self.subTasksGiven      = {}

        self.previewFilePath    = None
        self.env = env


    def initialize( self ):
        pass

    #######################
    def queryExtraData( self, perfIndex ):

        perf = max( int( float( perfIndex ) / 500 ), 1)
        endTask = min( self.lastTask + perf, self.totalTasks )

        commonPathPrefix = os.path.commonprefix( self.taskResources )
        commonPathPrefix = os.path.dirname( commonPathPrefix )

        sceneSrc = regenerateFile( self.sceneFileSrc, self.resX, self.resY, self.pixelFilter, self.sampler, self.samplesPerPixel )

        extraData =          {      "pathRoot" : self.pathRoot,
                                    "startTask" : self.lastTask,
                                    "endTask" : endTask,
                                    "totalTasks" : self.totalTasks,
                                    "numSubtasks" : self.numSubtasks,
                                    "numCores" : self.numCores,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFileSrc" : sceneSrc
                                }



        hash = "{}".format( random.getrandbits(128) )
        self.subTasksGiven[ hash ] = extraData
        self.lastTask = endTask # TODO: Should depend on performance

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
        print ctd.workingDirectory

        # ctd.workingDirectory = ""


        return ctd


    #######################
    def queryExtraDataForTestTask( self ):

        sceneSrc = regenerateFile( self.sceneFileSrc, 5, 5, self.pixelFilter, self.sampler, self.samplesPerPixel )

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

        self.testTaskResPath = GNREnv.getTestTaskDirectory()
        self.testTaskResPath = unicode( os.path.abspath( self.testTaskResPath ) )
        print self.testTaskResPath
        if not os.path.exists( self.testTaskResPath ):
            os.makedirs( self.testTaskResPath )

        ctd.workingDirectory = os.path.relpath( self.mainProgramFile, self.testTaskResPath)
        ctd.workingDirectory    = os.path.dirname( ctd.workingDirectory )

        return ctd

    #######################
    def __shortExtraDataRepr( self, perfIndex, extraData ):
        l = extraData
        return "pathRoot: {}, startTask: {}, endTask: {}, totalTasks: {}, numSubtasks: {}, numCores: {}, outfilebasename: {}, sceneFileSrc: {}".format( l["pathRoot"], l["startTask"], l["endTask"], l["totalTasks"], l["numSubtasks"], l["numCores"], l["outfilebasename"], l["sceneFileSrc"] )

    #######################
    def needsComputation( self ):
        return self.lastTask != self.totalTasks

    #######################
    def computationStarted( self, extraData ):
        pass

    #######################
    def computationFinished( self, subtaskId, taskResult, env = None ):

        tmpDir = env.getTaskTemporaryDir( self.header.taskId )

        if len( taskResult ) > 0:
            for trp in taskResult:
                tr = pickle.loads( trp )
                fh = open( os.path.join( tmpDir, tr[ 0 ] ), "wb" )
                fh.write( decompress( tr[ 1 ] ) )
                fh.close()

                self.collector.acceptTask( os.path.join( tmpDir, tr[ 0 ] ) ) # pewnie tutaj trzeba czytac nie zpliku tylko z streama
                self.numTasksReceived += 1

                self.__updatePreview( os.path.join( tmpDir, tr[ 0 ] ) )

        if self.numTasksReceived == self.totalTasks:
            outputFileName = u"{}".format( self.outputFile, self.outputFormat )
            self.collector.finalize().save( outputFileName, self.outputFormat )
            self.previewFilePath = outputFileName

    #######################
    def getTotalTasks( self ):
        return self.totalTasks

    #######################
    def getTotalChunks( self ):
        return self.totalTasks

    #######################
    def getActiveTasks( self ):
        return self.lastTask

    #######################
    def getActiveChunks( self ):
        return self.lastTask

    #######################
    def getChunksLeft( self ):
        return self.totalTasks - self.lastTask

    #######################
    def getProgress( self ):
        return float( self.lastTask ) / self.totalTasks

    #######################
    def prepareResourceDelta( self, taskId, resourceHeader ):
        if taskId == self.header.taskId:
            commonPathPrefix = os.path.commonprefix( self.taskResources )
            commonPathPrefix = os.path.dirname( commonPathPrefix )
            dirName = commonPathPrefix #os.path.join( "res", self.header.clientId, self.header.taskId, "resources" )
            tmpDir = self.env.getTmpPath(self.header.clientId, self.header.taskId)

            if not os.path.exists( tmpDir ):
                os.makedirs( tmpDir )

            if os.path.exists( dirName ):
                return prepareDeltaZip( dirName, resourceHeader, tmpDir, self.taskResources )
            else:
                return None
        else:
            return None

    #######################
    def __updatePreview( self, newChunkFilePath ):

        if newChunkFilePath.endswith(".exr"):
            img = exr_to_pil( newChunkFilePath )
        else:
            img = Image.open( newChunkFilePath )

        tmpDir = self.env.getTmpPath( self.header.clientId, self.header.taskId )

        self.previewFilePath = "{}".format( os.path.join( tmpDir, "current_preview") )

        if os.path.exists( self.previewFilePath ):
            imgCurrent = Image.open( self.previewFilePath )
            imgCurrent = ImageChops.add( imgCurrent, img )
            imgCurrent.save( self.previewFilePath, "BMP" )
        else:
            img.save( self.previewFilePath, "BMP" )

    #######################
    def getPreviewFilePath( self ):
        return self.previewFilePath


def exr_to_pil( exrFile ):

    file = OpenEXR.InputFile( exrFile )
    pt = Imath.PixelType( Imath.PixelType.FLOAT )
    dw = file.header()['dataWindow']
    size = ( dw.max.x - dw.min.x + 1, dw.max.y - dw.min.y + 1 )

    rgbf = [Image.fromstring("F", size, file.channel(c, pt)) for c in "RGB"]

    #extrema = [im.getextrema() for im in rgbf]
    #darkest = min([lo for (lo,hi) in extrema])
    #lighest = max([hi for (lo,hi) in extrema])
    scale = 255.0
    def normalize_0_255(v):
        return (v * scale)
    rgb8 = [im.point(normalize_0_255).convert("L") for im in rgbf]
    return Image.merge("RGB", rgb8)
