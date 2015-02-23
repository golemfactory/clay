import logging
import random
import os
import tempfile

from collections import OrderedDict
from PIL import Image, ImageChops

from golem.core.simpleexccmd import execCmd
from golem.task.TaskState import SubtaskStatus
from golem.environments.Environment import Environment

from  examples.gnr.RenderingTaskState import RendererDefaults, RendererInfo
from examples.gnr.RenderingEnvironment import LuxRenderEnvironment
from examples.gnr.RenderingDirManager import getTestTaskPath
from examples.gnr.task.ImgRepr import loadImg, blend
from  examples.gnr.task.GNRTask import GNROptions, checkSubtaskIdWrapper
from  examples.gnr.task.RenderingTask import RenderingTask, RenderingTaskBuilder
from examples.gnr.task.SceneFileEditor import regenerateLuxFile
from examples.gnr.ui.LuxRenderDialog import LuxRenderDialog
from examples.gnr.customizers.LuxRenderDialogCustomizer import LuxRenderDialogCustomizer

logger = logging.getLogger(__name__)

##############################################
def buildLuxRenderInfo():
    defaults = RendererDefaults()
    defaults.outputFormat = "EXR"
    defaults.mainProgramFile = os.path.normpath( os.path.join( os.environ.get('GOLEM'), 'examples/tasks/luxTask.py') )
    defaults.minSubtasks = 1
    defaults.maxSubtasks = 100
    defaults.defaultSubtasks = 5

    renderer = RendererInfo( "LuxRender", defaults, LuxRenderTaskBuilder, LuxRenderDialog, LuxRenderDialogCustomizer, LuxRenderOptions )
    renderer.outputFormats = ["EXR", "PNG", "TGA"]
    renderer.sceneFileExt = [ "lxs" ]
    renderer.getTaskNumFromPixels = getTaskNumFromPixels
    renderer.getTaskBoarder = getTaskBoarder

    return renderer

def getTaskBoarder( startTask, endTask, totalTasks, resX = 300 , resY = 200, numSubtasks = 20):
    boarder = []
    for i in range( 0, resY ):
        boarder.append( (0, i ))
        boarder.append( (resX - 1, i) )
    for i in range(0, resX ):
        boarder.append( (i, 0))
        boarder.append( (i, resY - 1))
    return boarder

def getTaskNumFromPixels( pX, pY, totalTasks, resX = 300, resY = 200 ):
    return 1

##############################################
class LuxRenderOptions( GNROptions ):

    #######################
    def __init__( self ):
        self.environment = LuxRenderEnvironment()
        self.halttime = 600
        self.haltspp = 1
        self.sendBinaries = False
        self.luxconsole = self.environment.getLuxConsole()

    #######################
    def addToResources( self, resources ):
        if self.sendBinaries and os.path.isfile( self.luxconsole ):
            resources.add( os.path.normpath( self.luxconsole ) )
        return resources

    #######################
    def removeFromResources( self, resources ):
        if self.sendBinaries and os.path.normpath( self.luxconsole ) in resources:
            resources.remove( os.path.normpath( self.luxconsole ) )
        return resources

##############################################
class LuxRenderTaskBuilder( RenderingTaskBuilder ):
    #######################
    def build( self ):
        mainSceneDir = os.path.dirname( self.taskDefinition.mainSceneFile )

        luxTask = LuxTask(  self.clientId,
                            self.taskDefinition.taskId,
                            mainSceneDir,
                            self.taskDefinition.mainSceneFile,
                            self.taskDefinition.mainProgramFile,
                            self._calculateTotal( buildLuxRenderInfo(), self.taskDefinition ),
                            self.taskDefinition.resolution[0],
                            self.taskDefinition.resolution[1],
                            os.path.splitext( os.path.basename( self.taskDefinition.outputFile ))[0],
                            self.taskDefinition.outputFile,
                            self.taskDefinition.outputFormat,
                            self.taskDefinition.fullTaskTimeout,
                            self.taskDefinition.subtaskTimeout,
                            self.taskDefinition.resources,
                            self.taskDefinition.estimatedMemory,
                            self.rootPath,
                            self.taskDefinition.rendererOptions.halttime,
                            self.taskDefinition.rendererOptions.haltspp,
                            self.taskDefinition.rendererOptions.sendBinaries,
                            self.taskDefinition.rendererOptions.luxconsole
        )

        return self._setVerificationOptions( luxTask )

##############################################
class LuxTask( RenderingTask ):
    #######################
    def __init__(   self,
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
                    halttime,
                    haltspp,
                    ownBinaries,
                    luxconsole,
                    returnAddress = "",
                    returnPort = 0):

        RenderingTask.__init__( self, clientId, taskId, returnAddress, returnPort,
                                 LuxRenderEnvironment.getId(), fullTaskTimeout, subtaskTimeout,
                                 mainProgramFile, taskResources, mainSceneDir, mainSceneFile,
                                 totalTasks, resX, resY, outfilebasename, outputFile, outputFormat,
                                 rootPath, estimatedMemory )

        self.halttime = halttime
        self.haltspp = haltspp
        self.ownBinaries = ownBinaries
        self.luxconsole = luxconsole

        try:
            with open( mainSceneFile ) as f:
                self.sceneFileSrc = f.read()
        except Exception, err:
            logger.error( "Wrong scene file: {}".format( str( err ) ) )
            self.sceneFileSrc = ""

        self.outputFile, _ = os.path.splitext( self.outputFile )
        self.numAdd = 0

        self.previewEXR = None
        if self.ownBinaries:
            self.header.environment = Environment.getId()

    #######################
    def queryExtraData( self, perfIndex, numCores = 0, clientId = None ):
        if not self._acceptClient( clientId ):
            logger.warning(" Client {} banned from this task ".format( clientId ) )
            return None

        startTask, endTask = self._getNextTask()
        if startTask is None or endTask is None:
            logger.error("Task already computed")
            return None

        workingDirectory = self._getWorkingDirectory()
        minX = 0
        maxX = 1
        minY = (startTask - 1) * (1.0 / float( self.totalTasks ))
        maxY = (endTask ) * (1.0 / float( self.totalTasks))

        if self.halttime > 0:
            writeInterval =  int( self.halttime / 2)
        else:
            writeInterval = 60
        sceneSrc = regenerateLuxFile( self.sceneFileSrc, self.resX, self.resY, self.halttime, self.haltspp, writeInterval, [0, 1, 0, 1], "PNG" )
        sceneDir= os.path.dirname(self._getSceneFileRelPath())

        if self.ownBinaries:
            luxConsole = self._getLuxConsoleRelPath()
        else:
            luxConsole = 'luxconsole.exe'

        numThreads = max( numCores, 1 )

        extraData =          {      "pathRoot" : self.mainSceneDir,
                                    "startTask" : startTask,
                                    "endTask" : endTask,
                                    "totalTasks" : self.totalTasks,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFileSrc" : sceneSrc,
                                    "sceneDir": sceneDir,
                                    "numThreads": numThreads,
                                    "ownBinaries": self.ownBinaries,
                                    "luxConsole": luxConsole
                                }

        hash = "{}".format( random.getrandbits(128) )
        self.subTasksGiven[ hash ] = extraData
        self.subTasksGiven[ hash ][ 'status' ] = SubtaskStatus.starting
        self.subTasksGiven[ hash ][ 'perf' ] = perfIndex
        self.subTasksGiven[ hash ][ 'clientId' ] = clientId

        return self._newComputeTaskDef( hash, extraData, workingDirectory, perfIndex )


    #######################
    def queryExtraDataForTestTask( self ):
        self.testTaskResPath = getTestTaskPath( self.rootPath )
        logger.debug( self.testTaskResPath )
        if not os.path.exists( self.testTaskResPath ):
            os.makedirs( self.testTaskResPath )

        sceneSrc = regenerateLuxFile( self.sceneFileSrc, 1, 1, 5, 0, 1, [0, 1, 0, 1 ], "PNG")
        workingDirectory = self._getWorkingDirectory()
        sceneDir= os.path.dirname(self._getSceneFileRelPath())

        if self.ownBinaries:
            luxConsole = self._getLuxConsoleRelPath()
        else:
            luxConsole = 'luxconsole.exe'

        extraData = {
            "pathRoot" : self.mainSceneDir,
            "startTask": 1,
            "endTask": 1,
            "totalTasks": 1,
            "outfilebasename": self.outfilebasename,
            "sceneFileSrc": sceneSrc,
            "sceneDir": sceneDir,
            "numThreads": 1,
            "ownBinaries": self.ownBinaries,
            "luxConsole": luxConsole
        }

        hash = "{}".format( random.getrandbits(128) )


        return self._newComputeTaskDef( hash, extraData, workingDirectory, 0 )

    #######################
    def _shortExtraDataRepr( self, perfIndex, extraData ):
        l = extraData
        return "startTask: {}, outfilebasename: {}, sceneFileSrc: {}".format( l['startTask'], l['outfilebasename'], l['sceneFileSrc'])

    #######################
    def computationFinished(self, subtaskId, taskResult, dirManager = None, resultType = 0):
        tmpDir = dirManager.getTaskTemporaryDir( self.header.taskId, create = False )
        self.tmpDir = tmpDir

        trFiles = self.loadTaskResults( taskResult, resultType, tmpDir )

        if len( taskResult ) > 0:
            numStart = self.subTasksGiven[ subtaskId ][ 'startTask' ]
            self.subTasksGiven[ subtaskId ][ 'status' ] = SubtaskStatus.finished
            for trFile in trFiles:
                _, ext = os.path.splitext( trFile )
                if ext == '.flm':
                    self.collectedFileNames[ numStart ] = trFile
                    self.numTasksReceived += 1
                    self.countingNodes[ self.subTasksGiven[ subtaskId ][ 'clientId' ] ] = 1
                else:
                    self.subTasksGiven[ subtaskId ][ 'previewFile' ] = trFile
                    self._updatePreview( trFile, numStart )
        else:
            self._markSubtaskFailed( subtaskId )

        if self.numTasksReceived == self.totalTasks:
            self.__generateFinalFLM()
            self.__generateFinalFile()

    #######################
    def __generateFinalFLM( self ):
        outputFileName = u"{}".format( self.outputFile, self.outputFormat )
        self.collectedFileNames = OrderedDict( sorted( self.collectedFileNames.items() ) )
        files = " ".join( self.collectedFileNames.values() )
        env = LuxRenderEnvironment()
        luxMerger = env.getLuxMerger()
        if luxMerger is not None:
            cmd = "{} -o {}.flm {}".format( luxMerger, self.outputFile, files )

            logger.debug("Lux Merger cmd: {}".format( cmd ))
            execCmd( cmd )

    #######################
    def __generateFinalFile( self ):

        if self.halttime > 0:
            writeInterval =  int( self.halttime / 2)
        else:
            writeInterval = 60

        sceneSrc = regenerateLuxFile( self.sceneFileSrc, self.resX, self.resY, self.halttime, self.haltspp, writeInterval, [0, 1, 0, 1], self.outputFormat )

        tmpSceneFile = self.__writeTmpSceneFile( sceneSrc )
        self.__formatLuxRenderCmd( tmpSceneFile )

    #######################
    def __writeTmpSceneFile(self, sceneFileSrc ):
        tmpSceneFile = tempfile.TemporaryFile( suffix = ".lxs", dir = os.path.dirname( self.mainSceneFile ) )
        tmpSceneFile.close()
        with open(tmpSceneFile.name, 'w') as f:
            f.write( sceneFileSrc )
        return tmpSceneFile.name

    #######################
    def __formatLuxRenderCmd(self, sceneFile ):
        cmdFile = LuxRenderEnvironment().getLuxConsole()
        outputFLM = "{}.flm".format( self.outputFile )
        cmd = '"{}" "{}" -R "{}" -o "{}" '.format( cmdFile, sceneFile, outputFLM, self.outputFile)
        logger.debug("Last flm cmd {}".format( cmd ) )
        prevPath = os.getcwd()
        os.chdir( os.path.dirname( self.mainSceneFile ))
        execCmd( cmd )
        os.chdir( prevPath )

    #######################
    def _updatePreview( self, newChunkFilePath, chunkNum ):
        self.numAdd += 1
        if newChunkFilePath.endswith(".exr"):
            self.__updatePreviewFromEXR( newChunkFilePath )
        else:
            self.__updatePreviewFromPILFile( newChunkFilePath )

    #######################
    def __updatePreviewFromPILFile( self, newChunkFilePath ):
        img = Image.open( newChunkFilePath )

        imgCurrent = self._openPreview()
        imgCurrent = ImageChops.blend( imgCurrent, img, 1.0 / float(self.numAdd) )
        imgCurrent.save( self.previewFilePath, "BMP" )

    #######################
    def __updatePreviewFromEXR( self, newChunkFile ):
        if self.previewEXR is None:
            self.previewEXR = loadImg( newChunkFile )
        else:
            self.previewEXR = blend( self.previewEXR, loadImg( newChunkFile ), 1.0 / float( self.numAdd ) )

        imgCurrent = self._openPreview()
        img = self.previewEXR.toPIL()
        img.save( self.previewFilePath, "BMP")

    #######################
    @checkSubtaskIdWrapper
    def _removeFromPreview( self, subtaskId ):
        previewFiles = []
        for subId, task in self.subTasksGiven.iteritems():
            if subId != subtaskId and task['status'] == 'Finished' and 'previewFile' in task:
                previewFiles.append(task['previewFile'])

        self.previewFilePath = None
        self.numAdd = 0
        for f in previewFiles:
            self._updatePreview( f, None )

    #######################
    def _getLuxConsoleRelPath( self ):
        luxconsoleRel = os.path.relpath( os.path.dirname( self.luxconsole ), os.path.dirname( self.mainSceneFile ) )
        luxconsoleRel = os.path.join( luxconsoleRel, os.path.basename( self.luxconsole ) )
        return luxconsoleRel
