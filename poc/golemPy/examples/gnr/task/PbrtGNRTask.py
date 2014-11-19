import os
import random
import logging
import math

from examples.gnr.RenderingEnvironment import PBRTEnvironment

from examples.gnr.task.SceneFileEditor import regenerateFile

from GNRTask import GNROptions
from RenderingTask import RenderingTask, RenderingTaskBuilder
from RenderingDirManager import getTestTaskPath
from TaskState import RendererDefaults, RendererInfo
from examples.gnr.ui.PbrtDialog import PbrtDialog
from examples.gnr.customizers.PbrtDialogCustomizer import PbrtDialogCustomizer

logger = logging.getLogger(__name__)

##############################################
def buildPBRTRendererInfo():
    defaults = RendererDefaults()
    defaults.outputFormat       = "EXR"
    defaults.mainProgramFile    = os.path.normpath( os.path.join( os.environ.get( 'GOLEM' ), 'examples\\tasks\\pbrtTask.py' ) )
    defaults.minSubtasks        = 4
    defaults.maxSubtasks        = 200
    defaults.defaultSubtasks    = 60


    renderer                = RendererInfo( "PBRT", defaults, PbrtTaskBuilder, PbrtDialog, PbrtDialogCustomizer, PbrtRendererOptions )
    renderer.outputFormats  = [ "BMP", "EPS", "EXR", "GIF", "IM", "JPEG", "PCX", "PDF", "PNG", "PPM", "TIFF" ]
    renderer.sceneFileExt    = [ "pbrt" ]

    return renderer

##############################################
class PbrtRendererOptions(  GNROptions ):
    #######################
    def __init__( self ):
        self.pixelFilter = "mitchell"
        self.samplesPerPixelCount = 32
        self.algorithmType = "lowdiscrepancy"
        self.filters = [ "box", "gaussian", "mitchell", "sinc", "triangle" ]
        self.pathTracers = [ "adaptive", "bestcandidate", "halton", "lowdiscrepancy", "random", "stratified" ]

##############################################
class PbrtTaskBuilder( RenderingTaskBuilder ):
    #######################
    def build( self ):
        mainSceneDir = os.path.dirname( self.taskDefinition.mainSceneFile )

        pbrtTask = PbrtRenderTask( self.clientId,
                                   self.taskDefinition.taskId,
                                   mainSceneDir,
                                   self.taskDefinition.mainProgramFile,
                                   self._calculateTotal( buildPBRTRendererInfo(), self.taskDefinition ),
                                   20,
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
                                   self.taskDefinition.estimatedMemory,
                                   self.taskDefinition.outputFile,
                                   self.taskDefinition.outputFormat,
                                   self.rootPath
                                  )

        return pbrtTask

    #######################
    def _calculateTotal( self, renderer, definition ):

        if (not definition.optimizeTotal) and (renderer.defaults.minSubtasks <= definition.totalSubtasks <= renderer.defaults.maxSubtasks):
            return definition.totalSubtasks

        taskBase = 1000000
        allOp = definition.resolution[0] * definition.resolution[1] * definition.rendererOptions.samplesPerPixelCount
        return max( renderer.defaults.minSubtasks, min( renderer.defaults.maxSubtasks, allOp / taskBase ) )

##############################################
class PbrtRenderTask( RenderingTask ):

    #######################
    def __init__( self,
                  clientId,
                  taskId,
                  mainSceneDir,
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
                  estimatedMemory,
                  outputFile,
                  outputFormat,
                  rootPath,
                  returnAddress = "",
                  returnPort = 0
                  ):


        RenderingTask.__init__( self, clientId, taskId, returnAddress, returnPort,
                                PBRTEnvironment.getId(), fullTaskTimeout, subtaskTimeout,
                                mainProgramFile, taskResources, mainSceneDir, sceneFile,
                                totalTasks, resX, resY, outfilebasename, outputFile, outputFormat,
                                rootPath, estimatedMemory )

        self.collectedFileNames = []

        self.numSubtasks        = numSubtasks
        self.numCores           = numCores

        self.sceneFileSrc       = open(sceneFile).read()

        self.resX               = resX
        self.resY               = resY
        self.pixelFilter        = pixelFilter
        self.sampler            = sampler
        self.samplesPerPixel    = samplesPerPixel
        self.nx                 = self.totalTasks * self.numSubtasks
        self.ny                 = 1
        self.__countSubtaskReg()
        self.taskResX           = float( self.resX ) / float( self.nx )
        self.taskResY           = float( self.resY ) / float ( self.ny )

    #######################
    def queryExtraData( self, perfIndex, numCores = 0 ):

        startTask, endTask = self._getNextTask( perfIndex )

        if numCores == 0:
            numCores = self.numCores

        workingDirectory = self._getWorkingDirectory()
        sceneSrc = regenerateFile( self.sceneFileSrc, self.resX, self.resY, self.pixelFilter,
                                   self.sampler, self.samplesPerPixel )

        extraData =          {      "pathRoot" : self.mainSceneDir,
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
        self.subTasksGiven[ hash ][ 'status' ] = 'sent'

        self._updateTaskPreview()

        return self._newComputeTaskDef( hash, extraData, workingDirectory, perfIndex )

    #######################
    def queryExtraDataForTestTask( self ):

        workingDirectory = self._getWorkingDirectory()

        sceneSrc = regenerateFile( self.sceneFileSrc, 1, 1, self.pixelFilter, self.sampler,
                                   self.samplesPerPixel )

        extraData =          {      "pathRoot" : self.mainSceneDir,
                                    "startTask" : 0,
                                    "endTask" : 1,
                                    "totalTasks" : self.totalTasks,
                                    "numSubtasks" : self.numSubtasks,
                                    "numCores" : self.numCores,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFileSrc" : sceneSrc
                                }

        hash = "{}".format( random.getrandbits(128) )

        self.testTaskResPath = getTestTaskPath( self.rootPath )
        logger.debug( self.testTaskResPath )
        if not os.path.exists( self.testTaskResPath ):
            os.makedirs( self.testTaskResPath )

        return self._newComputeTaskDef( hash, extraData, workingDirectory, 0 )

    #######################
    def _getNextTask( self, perfIndex ):
        if self.lastTask != self.totalTasks :
            perf = max( int( float( perfIndex ) / 1500 ), 1)
            endTask = min( self.lastTask + perf, self.totalTasks )
            startTask = self.lastTask
            self.lastTask = endTask
        else:
            subtask = self.failedSubtasks.pop()
            self.numFailedSubtasks -= 1
            endTask = subtask.endChunk
            startTask = subtask.startChunk
        return startTask, endTask

    #######################
    def _shortExtraDataRepr( self, perfIndex, extraData ):
        l = extraData
        return "pathRoot: {}, startTask: {}, endTask: {}, totalTasks: {}, numSubtasks: {}, numCores: {}, outfilebasename: {}, sceneFileSrc: {}".format( l["pathRoot"], l["startTask"], l["endTask"], l["totalTasks"], l["numSubtasks"], l["numCores"], l["outfilebasename"], l["sceneFileSrc"] )

    #######################
    def computationFinished( self, subtaskId, taskResult, dirManager = None ):

        tmpDir = dirManager.getTaskTemporaryDir( self.header.taskId, create = False )

        if len( taskResult ) > 0:
            self.subTasksGiven[ subtaskId ][ 'status' ] = 'finished'
            for trp in taskResult:
                trFile = self._unpackTaskResult (trp, tmpDir )

                if self.outputFormat != "EXR":
                    self.collector.acceptTask( trFile ) # pewnie tutaj trzeba czytac nie zpliku tylko z streama
                else:
                    self.collectedFileNames.append( trFile )
                self.numTasksReceived += 1

                self._updatePreview( trFile )
                self._updateTaskPreview()

        if self.numTasksReceived == self.totalTasks:
            outputFileName = u"{}".format( self.outputFile, self.outputFormat )
            if self.outputFormat != "EXR":
                self.collector.finalize().save( outputFileName, self.outputFormat )
                self.previewFilePath = outputFileName
            else:
                files = " ".join( self.collectedFileNames )
                self._putCollectedFilesTogether( outputFileName, files, "add" )

    def _markTaskArea(self, subtask, imgTask, color ):
        for numTask in range( subtask['startTask'], subtask['endTask'] ):
            for sb in range(0, self.numSubtasks):
                num = self.numSubtasks * numTask + sb
                tx = num % self.nx
                ty = num / self.nx
                xL = tx * self.taskResX
                xR = (tx + 1) * self.taskResX
                yL = ty * self.taskResY
                yR = (ty + 1) * self.taskResY

                for i in range( int( math.floor(xL) ) , int( math.floor(xR) ) ):
                    for j in range( int( math.floor( yL )) , int( math.floor( yR ) ) ) :
                        imgTask.putpixel( (i, j), color )

    def __countSubtaskReg( self ):
        while ( self.nx % 2 == 0 ) and (2 * self.resX * self.ny < self.resY * self.nx ):
            self.nx /= 2
            self.ny *= 2
