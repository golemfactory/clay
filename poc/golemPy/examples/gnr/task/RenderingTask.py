import os
import logging
import pickle
import subprocess

from RenderingDirManager import getTmpPath
from GNRTask import GNRTask, GNRTaskBuilder
from golem.task.TaskBase import ComputeTaskDef
from RenderingTaskCollector import RenderingTaskCollector, exr_to_pil
from golem.core.Compress import decompress

from PIL import Image, ImageChops

MIN_TIMEOUT = 2200.0
SUBTASK_TIMEOUT = 220.0

logger = logging.getLogger(__name__)

class RenderingTaskBuilder( GNRTaskBuilder ):
    def _calculateTotal (self, renderer, definition ):
        if definition.optimizeTotal:
            return renderer.defaults.defaultSubtasks

        if renderer.defaults.minSubtasks <= definition.totalSubtasks <= renderer.defaults.maxSubtasks:
            return definition.totalSubtasks
        else :
            return renderer.defaults.defaultSubtasks


class RenderingTask( GNRTask ):
    #######################
    def __init__( self, clientId, taskId, ownerAddress, ownerPort, environment, ttl,
                  subtaskTtl, mainProgramFile, taskResources, mainSceneDir, mainSceneFile,
                  totalTasks, resX, resY, outfilebasename, outputFile, outputFormat, rootPath,
                  estimatedMemory ):

        srcFile = open( mainProgramFile, "r" )
        srcCode = srcFile.read()

        resourceSize = 0
        for resource in taskResources:
            resourceSize += os.stat(resource).st_size

        GNRTask.__init__( self, srcCode, clientId, taskId, ownerAddress, ownerPort, environment,
                          ttl, subtaskTtl, resourceSize, estimatedMemory )

        self.fullTaskTimeout        = ttl
        self.header.ttl             = self.fullTaskTimeout
        self.header.subtaskTimeout  = subtaskTtl

        self.mainProgramFile        = mainProgramFile
        self.mainSceneFile          = mainSceneFile
        self.mainSceneDir           = mainSceneDir
        self.outfilebasename        = outfilebasename
        self.outputFile             = outputFile
        self.outputFormat           = outputFormat

        self.totalTasks             = totalTasks
        self.resX                   = resX
        self.resY                   = resY

        self.rootPath               = rootPath
        self.previewFilePath        = None
        self.previewTaskFilePath    = None

        self.taskResources          = taskResources

        self.collector              = RenderingTaskCollector()
        self.collectedFileNames     = {}

    #######################
    def restart( self ):
        GNRTask.restart( self )
        self.previewFilePath = None
        self.previewTaskFilePath = None

        self.collector = RenderingTaskCollector()
        self.collectedFileNames = {}

    def updateTaskState( self, taskState ):
        if not self.finishedComputation() and self.previewTaskFilePath:
            taskState.extraData['resultPreview'] = self.previewTaskFilePath
        elif self.previewFilePath:
            taskState.extraData['resultPreview'] = self.previewFilePath

    #######################
    def _updatePreview( self, newChunkFilePath ):

        if newChunkFilePath.endswith(".exr"):
            img = exr_to_pil( newChunkFilePath )
        else:
            img = Image.open( newChunkFilePath )

        tmpDir = getTmpPath( self.header.clientId, self.header.taskId, self.rootPath )

        self.previewFilePath = "{}".format( os.path.join( tmpDir, "current_preview") )

        if os.path.exists( self.previewFilePath ):
            imgCurrent = Image.open( self.previewFilePath )
            imgCurrent = ImageChops.add( imgCurrent, img )
            imgCurrent.save( self.previewFilePath, "BMP" )

        else:
            img.save( self.previewFilePath, "BMP" )

    def _updateTaskPreview( self ):
        sentColor = (0, 255, 0)
        failedColor = (255, 0, 0)

        tmpDir = getTmpPath( self.header.clientId, self.header.taskId, self.rootPath )
        self.previewTaskFilePath = "{}".format( os.path.join( tmpDir, "current_task_preview") )
        if self.previewFilePath and os.path.exists( self.previewFilePath ):
            imgTask = Image.open( self.previewFilePath )
            for sub in self.subTasksGiven.values():
                if sub['status'] == 'sent':
                    self._markTaskArea( sub, imgTask, sentColor )
                if sub['status'] == 'failed':
                    self._markTaskArea( sub, imgTask, failedColor )

            imgTask.save( self.previewTaskFilePath, "BMP" )
            print self.previewTaskFilePath


    def _markTaskArea(self, subtask, imgTask, color ):
        upper = ( self.resY / self.totalTasks ) * (subtask[ 'startTask' ] - 1)
        lower = ( self.resY / self.totalTasks ) * ( subtask[ 'endTask' ] )
        for i in range(0, self.resX ):
            for j in range( upper, lower):
                imgTask.putpixel( (i, j), color )

    #######################
    def _unpackTaskResult( self, trp, tmpDir ):
        tr = pickle.loads( trp )
        fh = open( os.path.join( tmpDir, tr[ 0 ] ), "wb" )
        fh.write( decompress( tr[ 1 ] ) )
        fh.close()
        return os.path.join( tmpDir, tr[0] )

    #######################
    def _putCollectedFilesTogether( self, outputFileName, files, arg ):
        taskCollectorPath = os.path.join( os.environ.get( 'GOLEM' ), "tools\\taskcollector\Release\\taskcollector.exe" )
        cmd = u"{} {} {} {}".format(taskCollectorPath, arg, outputFileName, files )
        logger.debug( cmd )
        pc = subprocess.Popen( cmd )
        pc.wait()

    #######################
    def _newComputeTaskDef( self, hash, extraData, workingDirectory, perfIndex ):
        ctd = ComputeTaskDef()
        ctd.taskId              = self.header.taskId
        ctd.subtaskId           = hash
        ctd.extraData           = extraData
        ctd.returnAddress       = self.header.taskOwnerAddress
        ctd.returnPort          = self.header.taskOwnerPort
        ctd.shortDescription    = self._shortExtraDataRepr( perfIndex, extraData )
        ctd.srcCode             = self.srcCode
        ctd.performance         = perfIndex
        ctd.workingDirectory    = workingDirectory
        return ctd

    #######################
    def _getNextTask( self ):
        if self.lastTask != self.totalTasks:
            self.lastTask += 1
            startTask = self.lastTask
            endTask = self.lastTask
        else:
            subtask = self.failedSubtasks.pop()
            self.numFailedSubtasks -= 1
            endTask = subtask.endChunk
            startTask = subtask.startChunk
        return startTask, endTask

    #######################
    def _getWorkingDirectory( self ):
        commonPathPrefix = os.path.commonprefix( self.taskResources )
        commonPathPrefix = os.path.dirname( commonPathPrefix )

        workingDirectory    = os.path.relpath( self.mainProgramFile, commonPathPrefix )
        workingDirectory    = os.path.dirname( workingDirectory )
        return workingDirectory

    #######################
    def _getSceneFileRelPath( self ):
        sceneFile = os.path.relpath( os.path.dirname(self.mainSceneFile), os.path.dirname( self.mainProgramFile ) )
        sceneFile = os.path.join( sceneFile, os.path.basename( self.mainSceneFile ) )
        return sceneFile

    ########################
    def _shortExtraDataRepr( self, perfIndex, extraData ):
        l = extraData
        return "pathRoot: {}, startTask: {}, endTask: {}, totalTasks: {}, outfilebasename: {}, sceneFile: {}".format( l["pathRoot"], l["startTask"], l["endTask"], l["totalTasks"], l["outfilebasename"], l["sceneFile"] )
