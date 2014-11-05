import os
import logging

from GNREnv import GNREnv
from GNRTask import GNRTask, GNRTaskBuilder
from RenderingTaskCollector import RenderingTaskCollector, exr_to_pil

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

        self.fullTaskTimeout        = max( MIN_TIMEOUT, ttl )
        self.header.ttl             = self.fullTaskTimeout
        self.header.subtaskTimeout  = max( SUBTASK_TIMEOUT, subtaskTtl )

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

        self.taskResources          = taskResources

        self.collector              = RenderingTaskCollector()
        self.collectedFileNames     = {}

    #######################
    def restart( self ):
        GNRTask.restart( self )
        self.previewFilePath = None

        self.collector = RenderingTaskCollector()
        self.collectedFileNames = []

    #######################
    def _updatePreview( self, newChunkFilePath ):

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