import os
import random
import logging
import math

from golem.task.TaskState import SubtaskStatus

from examples.gnr.RenderingEnvironment import PBRTEnvironment
from examples.gnr.RenderingDirManager import getTestTaskPath
from examples.gnr.RenderingTaskState import RendererDefaults, RendererInfo, RenderingTaskDefinition
from examples.gnr.task.SceneFileEditor import regeneratePbrtFile
from examples.gnr.task.GNRTask import GNROptions, GNRTaskBuilder
from examples.gnr.task.RenderingTask import RenderingTask, RenderingTaskBuilder
from examples.gnr.task.RenderingTaskCollector import RenderingTaskCollector
from examples.gnr.ui.PbrtDialog import PbrtDialog
from examples.gnr.customizers.PbrtDialogCustomizer import PbrtDialogCustomizer


logger = logging.getLogger(__name__)

##############################################
def buildPBRTRendererInfo():
    defaults = RendererDefaults()
    defaults.outputFormat       = "EXR"
    defaults.mainProgramFile    = os.path.normpath( os.path.join( os.environ.get( 'GOLEM' ), 'examples/tasks/pbrtTask.py' ) )
    defaults.minSubtasks        = 4
    defaults.maxSubtasks        = 200
    defaults.defaultSubtasks    = 60


    renderer                = RendererInfo( "PBRT", defaults, PbrtTaskBuilder, PbrtDialog, PbrtDialogCustomizer, PbrtRendererOptions )
    renderer.outputFormats  = [ "BMP", "EPS", "EXR", "GIF", "IM", "JPEG", "PCX", "PDF", "PNG", "PPM", "TIFF" ]
    renderer.sceneFileExt    = [ "pbrt" ]
    renderer.getTaskNumFromPixels = getTaskNumFromPixels
    renderer.getTaskBoarder = getTaskBoarder

    return renderer

##############################################
class PbrtRendererOptions(  GNROptions ):
    #######################
    def __init__( self ):
        self.pbrtPath = ''
        self.pixelFilter = "mitchell"
        self.samplesPerPixelCount = 32
        self.algorithmType = "lowdiscrepancy"
        self.filters = [ "box", "gaussian", "mitchell", "sinc", "triangle" ]
        self.pathTracers = [ "adaptive", "bestcandidate", "halton", "lowdiscrepancy", "random", "stratified" ]

    #######################
    def addToResources( self, resources ):
        if os.path.isfile( self.pbrtPath ):
            resources.add( os.path.normpath( self.pbrtPath ) )
        return resources

    #######################
    def removeFromResources( self, resources ):
        if os.path.normpath( self.pbrtPath ) in resources:
            resources.remove( os.path.normpath( self.pbrtPath ) )
        return resources

##############################################
class PbrtGNRTaskBuilder( GNRTaskBuilder ):
    def build( self ):
        if isinstance( self.taskDefinition, RenderingTaskDefinition ):
            rtd = self.taskDefinition
        else:
            rtd = self.__translateTaskDefinition()

        pbrtTaskBuilder = PbrtTaskBuilder( self.clientId, rtd, self.rootPath )
        return pbrtTaskBuilder.build()

    def __translateTaskDefinition( self ):
        rtd = RenderingTaskDefinition()
        rtd.taskId = self.taskDefinition.taskId
        rtd.fullTaskTimeout = self.taskDefinition.fullTaskTimeout
        rtd.subtaskTimeout = self.taskDefinition.subtaskTimeout
        rtd.minSubtaskTime = self.taskDefinition.minSubtaskTime
        rtd.resources = self.taskDefinition.resources
        rtd.estimatedMemory = self.taskDefinition.estimatedMemory
        rtd.totalSubtasks = self.taskDefinition.totalSubtasks
        rtd.optimizeTotal = self.taskDefinition.optimizeTotal
        rtd.mainProgramFile = self.taskDefinition.mainProgramFile
        rtd.taskType = self.taskDefinition.taskType
        rtd.verificationOptions = self.taskDefinition.verificationOptions

        rtd.resolution = self.taskDefinition.options.resolution
        rtd.renderer = self.taskDefinition.taskType
        rtd.mainSceneFile = self.taskDefinition.options.mainSceneFile
        rtd.resources.add( rtd.mainSceneFile )
        rtd.outputFile = self.taskDefinition.options.outputFile
        rtd.outputFormat = self.taskDefinition.options.outputFormat
        rtd.rendererOptions = PbrtRendererOptions()
        rtd.rendererOptions.pixelFilter = self.taskDefinition.options.pixelFilter
        rtd.rendererOptions.algorithmType = self.taskDefinition.options.algorithmType
        rtd.rendererOptions.samplesPerPixelCount = self.taskDefinition.options.samplesPerPixelCount
        rtd.rendererOptions.pbrtPath = self.taskDefinition.options.pbrtPath
        return rtd



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
                                   self.taskDefinition.rendererOptions.pbrtPath,
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

        return self._setVerificationOptions( pbrtTask )

    def _setVerificationOptions( self, newTask ):
        newTask = RenderingTaskBuilder._setVerificationOptions( self, newTask )
        if newTask.advanceVerification:
            boxX = min( newTask.verificationOptions.boxSize[0], newTask.taskResX )
            boxY = min( newTask.verificationOptions.boxSize[1], newTask.taskResY )
            newTask.boxSize = ( boxX, boxY )
        return newTask

    #######################
    def _calculateTotal( self, renderer, definition ):

        if (not definition.optimizeTotal) and (renderer.defaults.minSubtasks <= definition.totalSubtasks <= renderer.defaults.maxSubtasks):
            return definition.totalSubtasks

        taskBase = 1000000
        allOp = definition.resolution[0] * definition.resolution[1] * definition.rendererOptions.samplesPerPixelCount
        return max( renderer.defaults.minSubtasks, min( renderer.defaults.maxSubtasks, allOp / taskBase ) )

def countSubtaskReg( totalTasks, subtasks, resX, resY ):
    nx = totalTasks * subtasks
    ny = 1
    while ( nx % 2 == 0 ) and (2 * resX * ny < resY * nx ):
        nx /= 2
        ny *= 2
    taskResX = float( resX ) / float( nx )
    taskResY = float( resY ) / float( ny )
    return nx, ny, taskResX, taskResY

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
                  pbrtPath,
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
                  returnPort = 0,
                  keyId = ""
                  ):


        RenderingTask.__init__( self, clientId, taskId, returnAddress, returnPort, keyId,
                                PBRTEnvironment.getId(), fullTaskTimeout, subtaskTimeout,
                                mainProgramFile, taskResources, mainSceneDir, sceneFile,
                                totalTasks, resX, resY, outfilebasename, outputFile, outputFormat,
                                rootPath, estimatedMemory )

        self.collectedFileNames = set()

        self.numSubtasks        = numSubtasks
        self.numCores           = numCores

        try:
            with open( sceneFile ) as f:
                self.sceneFileSrc = f.read()
        except Exception, err:
            logger.error( "Wrong scene file: {}".format( str( err ) ) )
            self.sceneFileSrc = ""

        self.resX               = resX
        self.resY               = resY
        self.pixelFilter        = pixelFilter
        self.sampler            = sampler
        self.samplesPerPixel    = samplesPerPixel
        self.pbrtPath           = pbrtPath
        self.nx, self.ny, self.taskResX, self.taskResY = countSubtaskReg( self.totalTasks, self.numSubtasks, self.resX, self.resY)

    #######################
    def queryExtraData( self, perfIndex, numCores = 0, clientId = None ):
        if not self._acceptClient( clientId ):
            logger.warning(" Client {} banned from this task ".format( clientId ) )
            return None


        startTask, endTask = self._getNextTask( perfIndex )
        if startTask is None or endTask is None:
            logger.error("Task already computed")
            return None

        if numCores == 0:
            numCores = self.numCores

        workingDirectory = self._getWorkingDirectory()
        sceneSrc = regeneratePbrtFile( self.sceneFileSrc, self.resX, self.resY, self.pixelFilter,
                                   self.sampler, self.samplesPerPixel )

        sceneDir= os.path.dirname(self._getSceneFileRelPath())

        pbrtPath = self.__getPbrtRelPath()

        extraData =          {      "pathRoot" : self.mainSceneDir,
                                    "startTask" : startTask,
                                    "endTask" : endTask,
                                    "totalTasks" : self.totalTasks,
                                    "numSubtasks" : self.numSubtasks,
                                    "numCores" : numCores,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFileSrc" : sceneSrc,
                                    "sceneDir": sceneDir,
                                    "pbrtPath": pbrtPath
                                }

        hash = "{}".format( random.getrandbits(128) )
        self.subTasksGiven[ hash ] = extraData
        self.subTasksGiven[ hash ][ 'status' ] = SubtaskStatus.starting
        self.subTasksGiven[ hash ][ 'perf' ] = perfIndex
        self.subTasksGiven[ hash ][ 'clientId' ] = clientId

        self._updateTaskPreview()

        return self._newComputeTaskDef( hash, extraData, workingDirectory, perfIndex )

    #######################
    def queryExtraDataForTestTask( self ):

        workingDirectory = self._getWorkingDirectory()

        sceneSrc = regeneratePbrtFile( self.sceneFileSrc, 1, 1, self.pixelFilter, self.sampler,
                                   self.samplesPerPixel )

        pbrtPath = self.__getPbrtRelPath()
        sceneDir= os.path.dirname(self._getSceneFileRelPath())

        extraData =          {      "pathRoot" : self.mainSceneDir,
                                    "startTask" : 0,
                                    "endTask" : 1,
                                    "totalTasks" : self.totalTasks,
                                    "numSubtasks" : self.numSubtasks,
                                    "numCores" : self.numCores,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFileSrc" : sceneSrc,
                                    "sceneDir": sceneDir,
                                    "pbrtPath": pbrtPath
                                }

        hash = "{}".format( random.getrandbits(128) )

        self.testTaskResPath = getTestTaskPath( self.rootPath )
        logger.debug( self.testTaskResPath )
        if not os.path.exists( self.testTaskResPath ):
            os.makedirs( self.testTaskResPath )

        return self._newComputeTaskDef( hash, extraData, workingDirectory, 0 )

    #######################
    def computationFinished( self, subtaskId, taskResult, dirManager = None, resultType = 0 ):

        if not self.shouldAccept( subtaskId ):
            return

        tmpDir = dirManager.getTaskTemporaryDir( self.header.taskId, create = False )
        self.tmpDir = tmpDir
        trFiles = self.loadTaskResults( taskResult, resultType, tmpDir )

        if not self._verifyImgs( subtaskId, trFiles ):
            self._markSubtaskFailed( subtaskId )
            self._updateTaskPreview()
            return

        if len( taskResult ) > 0:
            self.subTasksGiven[ subtaskId ][ 'status' ] = SubtaskStatus.finished
            for trFile in trFiles:

                self.collectedFileNames.add( trFile )
                self.numTasksReceived += 1
                self.countingNodes[ self.subTasksGiven[ subtaskId ][ 'clientId' ] ] = 1

                self._updatePreview( trFile )
                self._updateTaskPreview()
        else:
            self._markSubtaskFailed( subtaskId )
            self._updateTaskPreview()

        if self.numTasksReceived == self.totalTasks:
            outputFileName = u"{}".format( self.outputFile, self.outputFormat )
            if self.outputFormat != "EXR":
                collector = RenderingTaskCollector()
                for file in self.collectedFileNames:
                    collector.acceptTask( file )
                collector.finalize().save( outputFileName, self.outputFormat )
                self.previewFilePath = outputFileName
            else:
                self._putCollectedFilesTogether( outputFileName, list( self.collectedFileNames ), "add" )

    #######################
    def restart( self ):
        RenderingTask.restart( self )
        self.collectedFileNames = set()

    #######################
    def restartSubtask( self, subtaskId ):
        if self.subTasksGiven[ subtaskId ][ 'status' ] == SubtaskStatus.finished:
            self.numTasksReceived += 1
        RenderingTask.restartSubtask( self, subtaskId )
        self._updateTaskPreview()

    #######################
    def getPriceMod( self, subtaskId ):
        if subtaskId not in self.subTasksGiven:
            logger.error( "Not my subtask {}".format( subtaskId ) )
            return 0
        perf =  (self.subTasksGiven[ subtaskId ]['endTask'] - self.subTasksGiven[ subtaskId ][ 'startTask' ])
        perf *= float( self.subTasksGiven[ subtaskId ]['perf'] ) / 1000
        return perf

    #######################
    def _getNextTask( self, perfIndex ):
        if self.lastTask != self.totalTasks :
            perf = max( int( float( perfIndex ) / 1500 ), 1)
            endTask = min( self.lastTask + perf, self.totalTasks )
            startTask = self.lastTask
            self.lastTask = endTask
            return startTask, endTask
        else:
            for sub in self.subTasksGiven.values():
                if sub['status'] == SubtaskStatus.failure:
                    sub['status'] = SubtaskStatus.resent
                    endTask = sub['endTask']
                    startTask = sub['startTask']
                    self.numFailedSubtasks -= 1
                    return startTask, endTask
        return None, None

    #######################
    def _shortExtraDataRepr( self, perfIndex, extraData ):
        l = extraData
        return "pathRoot: {}, startTask: {}, endTask: {}, totalTasks: {}, numSubtasks: {}, numCores: {}, outfilebasename: {}, sceneFileSrc: {}".format( l["pathRoot"], l["startTask"], l["endTask"], l["totalTasks"], l["numSubtasks"], l["numCores"], l["outfilebasename"], l["sceneFileSrc"] )

    #######################
    def _getPartImgSize( self, subtaskId, advTestFile ):
        if advTestFile is not None:
            numTask = self.__getNumFromFileName( advTestFile[0], subtaskId )
        else:
            numTask = self.subTasksGiven[ subtaskId ][ 'startTask' ]
        numSubtask = random.randint(0, self.numSubtasks - 1)
        num = numTask * self.numSubtasks + numSubtask
        x0 = int(  round( (num % self.nx) * self.taskResX ) )
        x1 = int(  round( ( ( num % self.nx ) + 1 ) * self.taskResX ) )
        y0 = int( math.floor( ( num / self.nx ) * self.taskResY ) )
        y1 = int ( math.floor( ( ( num / self.nx ) + 1 ) * self.taskResY ) )
        return x0, y0, x1, y1

    #######################
    def _markTaskArea(self, subtask, imgTask, color ):
        for numTask in range( subtask['startTask'], subtask['endTask'] ):
            for sb in range(0, self.numSubtasks):
                num = self.numSubtasks * numTask + sb
                tx = num % self.nx
                ty = num /  self.nx
                xL = tx * self.taskResX
                xR = (tx + 1) * self.taskResX
                yL = ty * self.taskResY
                yR = (ty + 1) * self.taskResY

                for i in range( int( round(xL) ) , int( round(xR) ) ):
                    for j in range( int( math.floor( yL )) , int( math.floor( yR ) ) ) :
                        imgTask.putpixel( (i, j), color )

    #######################
    def _changeScope( self, subtaskId, startBox, trFile ):
        extraData, startBox = RenderingTask._changeScope( self, subtaskId, startBox, trFile )
        extraData[ "outfilebasename" ] = str( extraData[ "outfilebasename" ] )
        extraData[ "resourcePath" ] = os.path.dirname( self.mainProgramFile )
        extraData[ "tmpPath" ] = self.tmpDir
        extraData[ "totalTasks" ] = self.totalTasks * self.numSubtasks
        extraData[ "numSubtasks" ] = 1
        extraData[ "startTask" ] = getTaskNumFromPixels( startBox[0], startBox[1], extraData[ "totalTasks" ], self.resX, self.resY, 1) - 1
        extraData[ "endTask" ] = extraData[ "startTask" ] + 1

        return extraData, startBox

    def __getPbrtRelPath( self ):
        pbrtRel = os.path.relpath( os.path.dirname( self.pbrtPath ), os.path.dirname( self.mainSceneFile ) )
        pbrtRel = os.path.join( pbrtRel, os.path.basename( self.pbrtPath ) )
        return pbrtRel


    #######################
    def __getNumFromFileName( self, file_, subtaskId ):
        try:
            fileName = os.path.basename( file_ )
            fileName, ext = os.path.splitext( fileName )
            BASENAME = "temp"
            idx = fileName.find( BASENAME )
            return int( fileName[idx + len( BASENAME ):] )
        except Exception, err:
            logger.error("Wrong output file name {}: {}".format( file_, str( err ) ) )
            return self.subTasksGiven[ subtaskId ][ 'startTask' ]

#####################################################################
def getTaskNumFromPixels( pX, pY, totalTasks, resX = 300, resY = 200, subtasks = 20):
    nx, ny, taskResX, taskResY = countSubtaskReg(totalTasks, subtasks, resX, resY)
    numX = int( math.floor( pX / taskResX ) )
    numY = int( math.floor( pY / taskResY ) )
    num = (numY * nx + numX) /subtasks + 1
    return num

#####################################################################
def getTaskBoarder(startTask, endTask, totalTasks, resX = 300, resY = 200, numSubtasks = 20):
    boarder = []
    newLeft = True
    lastRight = None
    for numTask in range( startTask, endTask ):
        for sb in range( numSubtasks ):
            num = numSubtasks * numTask + sb
            nx, ny, taskResX, taskResY = countSubtaskReg(totalTasks, numSubtasks, resX, resY)
            tx = num % nx
            ty = num /  nx
            xL = int( round( tx * taskResX ) )
            xR = int ( round( (tx + 1) * taskResX ) )
            yL = int ( round( ty * taskResY ) )
            yR = int( round( (ty + 1) * taskResY ) )
            for i in range( xL, xR ):
                if (i, yL) in boarder:
                    boarder.remove( (i, yL ) )
                else:
                    boarder.append( (i, yL ) )
                boarder.append( (i, yR) )
            if xL == 0:
                newLeft = True
            if newLeft:
                for i in range( yL, yR ):
                    boarder.append( (xL, i) )
                newLeft = False
            if xR == resY:
                for i in range( yL, yR ):
                    boarder.append( (xR, i) )
            lastRight = (xR, yL, yR)
    xR, yL, yR = lastRight
    for i in range( yL, yR ):
        boarder.append( (xR, i) )
    return boarder

