import os
import logging
import math

from examples.gnr.task.RenderingTask import RenderingTask, RenderingTaskBuilder
from examples.gnr.task.RenderingTaskCollector import exr_to_pil
from examples.gnr.RenderingDirManager import getTmpPath

from golem.task.TaskState import SubtaskStatus

from PIL import Image

logger = logging.getLogger(__name__)

##############################################
class FrameRenderingTaskBuiler( RenderingTaskBuilder ):
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
                    logger.warning("Too many subtasks for this task. {} subtasks will be used".format( est ) )
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
class FrameRenderingTask( RenderingTask ):
    #######################
    def __init__( self, clientId, taskId, ownerAddress, ownerPort, environment, ttl,
                  subtaskTtl, mainProgramFile, taskResources, mainSceneDir, mainSceneFile,
                  totalTasks, resX, resY, outfilebasename, outputFile, outputFormat, rootPath,
                  estimatedMemory, useFrames, frames ):
        RenderingTask.__init__( self, clientId, taskId, ownerAddress, ownerPort, environment, ttl,
                  subtaskTtl, mainProgramFile, taskResources, mainSceneDir, mainSceneFile,
                  totalTasks, resX, resY, outfilebasename, outputFile, outputFormat, rootPath,
                  estimatedMemory )

        self.useFrames = useFrames
        self.frames = frames

        if useFrames:
            self.previewFilePath = [ None ] * len ( frames )
            self.previewTaskFilePath = [ None ] * len( frames )

    #######################
    def restart( self ):
        RenderingTask.restart( self )
        if self.useFrames:
            self.previewFilePath = [ None ] * len ( self.frames )
            self.previewTaskFilePath = [ None ] * len ( self.frames )

    #######################
    def _updateFramePreview(self, newChunkFilePath, frameNum, part = 1, final = False ):
        num = self.frames.index(frameNum)
        if newChunkFilePath.endswith(".exr") or newChunkFilePath.endswith(".EXR"):
            img = exr_to_pil( newChunkFilePath )
        else:
            img = Image.open( newChunkFilePath )

        tmpDir = getTmpPath( self.header.clientId, self.header.taskId, self.rootPath )
        if self.previewFilePath[ num ] is None:
            self.previewFilePath[ num ] = "{}{}".format( os.path.join( tmpDir, "current_preview" ), num )
        if self.previewTaskFilePath[ num ] is None:
            self.previewTaskFilePath[ num ] = "{}{}".format( os.path.join( tmpDir, "current_task_preview" ) , num )

        if not final:
            img = self._pasteNewChunk( img, self.previewFilePath[ num ], part )

        img.save( self.previewFilePath[ num ], "BMP" )
        img.save( self.previewTaskFilePath[ num ], "BMP" )

    #######################
    def _updateFrameTaskPreview(self ):
        sentColor = (0, 255, 0)
        failedColor = (255, 0, 0)

        for sub in self.subTasksGiven.values():
            if sub['status'] == SubtaskStatus.starting:
                for frame in sub['frames']:
                    self.__markSubFrame( sub, frame, sentColor )

            if sub['status'] == SubtaskStatus.failure:
                for frame in sub['frames']:
                    self.__markSubFrame( sub, frame, failedColor )

    #######################
    def _openFramePreview( self, previewFilePath ):

        if not os.path.exists( previewFilePath ):
            img = Image.new("RGB", ( self.resX,self.resY ) )
            img.save( previewFilePath, "BMP" )

        return Image.open( previewFilePath )

    #######################
    def __markSubFrame( self, sub, frame, color  ):
        tmpDir = getTmpPath( self.header.clientId, self.header.taskId, self.rootPath )
        idx = self.frames.index( frame )
        previewTaskFilePath = "{}{}".format( os.path.join( tmpDir, "current_task_preview" ) , idx )
        previewFilePath = "{}{}".format( os.path.join( tmpDir, "current_preview"), idx )
        imgTask = self._openFramePreview( previewFilePath )
        self._markTaskArea( sub, imgTask, color )
        imgTask.save( previewTaskFilePath, "BMP" )
        self.previewTaskFilePath[ idx ] = previewTaskFilePath

    #######################
    def _markTaskArea(self, subtask, imgTask, color ):
        if not self.useFrames:
            RenderingTask._markTaskArea( self, subtask, imgTask, color )
        elif self.__fullFrames():
            for i in range( 0, self.resX ):
                for j in range( 0, self.resY ):
                    imgTask.putpixel( (i, j), color )
        else:
            parts = self.totalTasks / len( self.frames )
            upper = int( math.floor( float( self.resY ) /float( parts ) ) * ( ( subtask['startTask'] - 1) % parts ) )
            lower = int( math.floor( float( self.resY ) /float( parts ) ) * ( ( subtask['startTask'] - 1) % parts   + 1 ) )
            for i in range( 0, self.resX ):
                for j in range( upper, lower ):
                    imgTask.putpixel( (i, j), color )

    #######################
    def __fullFrames( self ):
        return self.totalTasks <= len( self.frames )

##############################################
def getTaskBoarder( startTask, endTask, totalTasks, resX = 300, resY = 200, useFrames = False, frames = 100, frameNum = 1):
    if not useFrames:
        boarder = __getBoarder( startTask, endTask, totalTasks, resX, resY )
    elif totalTasks > frames:
        parts = totalTasks / frames
        boarder = __getBoarder( (startTask - 1) % parts + 1, (endTask - 1) % parts + 1, parts, resX, resY)
    else:
        boarder = []

    return boarder

##############################################
def getTaskNumFromPixels( pX, pY, totalTasks, resX = 300, resY = 200, useFrames = False, frames = 100, frameNum = 1):
    if not useFrames:
        num = __numFromPixel(pY, resY, totalTasks)
    else:
        if totalTasks <= frames:
            subtaskFrames = int ( math.ceil( float( frames )  / float( totalTasks ) ) )
            num = int ( math.ceil( float( frameNum ) / subtaskFrames ) )
        else:
            parts = totalTasks / frames
            num = (frameNum - 1) * parts +  __numFromPixel( pY, resY, parts )
    return num

##############################################
def __getBoarder( startTask, endTask, parts, resX, resY ):
    boarder = []
    upper = int( math.floor( float(resY ) / float( parts )   * (startTask - 1) ) )
    lower = int( math.floor( float( resY ) / float( parts )  * endTask  ) )
    for i in range( upper, lower ):
        boarder.append( (0, i) )
        boarder.append( (resX, i) )
    for i in range( 0,  resX ):
        boarder.append( (i, upper) )
        boarder.append( (i, lower) )
    return boarder

##############################################
def __numFromPixel( pY, resY, tasks ):
    return int( math.floor( pY / math.floor( float( resY ) / float( tasks ) ) ) ) + 1
