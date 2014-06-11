import os
import random
import cPickle as pickle

from golem.task.TaskBase import TaskBuilder, ComputeTaskDef
from golem.task.TaskState import TaskStatus
from golem.core.Compress import decompress
from golem.task.resource.Resource import prepareDeltaZip


from GNRTask import GNRTask
from testtasks.pbrt.takscollector import PbrtTaksCollector



class PbrtTaskBuilder( TaskBuilder ):
    #######################
    def __init__( self, clientId, taskDefinition ):
        self.taskDefinition = taskDefinition
        self.clientId       = clientId

    #######################
    def build( self ):
        mainSceneDir = os.path.dirname( self.taskDefinition.mainSceneFile )

        # TODO: Calculate total task

        pbrtTask = PbrtRenderTask( self.clientId,
                                   self.taskDefinition.id,
                                   mainSceneDir,
                                   self.taskDefinition.mainProgramFile,
                                   10,
                                   45,
                                   1,
                                   "temp",
                                   self.taskDefinition.mainSceneFile,
                                   self.taskDefinition.fullTaskTimeout,
                                   self.taskDefinition.resources,
                                   self.taskDefinition.outputFile,
                                   self.taskDefinition.outputFormat )

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
                  outfilebasename,
                  sceneFile,
                  fullTaskTimeout,
                  taskResources,
                  outputFile,
                  outputFormat,
                  returnAddress = "",
                  returnPort = 0 ):

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
        self.sceneFile          = sceneFile
        self.taskResources      = taskResources
        self.mainProgramFile    = mainProgramFile
        self.outputFile         = outputFile
        self.outputFormat       = outputFormat

        self.collector          = PbrtTaksCollector()
        self.numTasksReceived   = 0
        self.subTasksGiven      = {}

        self.previewFilePath    = None


    def initialize( self ):
        pass

    #######################
    def queryExtraData( self, perfIndex ):

        endTask = min( self.lastTask + 1, self.totalTasks )

        commonPathPrefix = os.path.commonprefix( self.taskResources )
        commonPathPrefix = os.path.dirname( commonPathPrefix )

        extraData =          {      "pathRoot" : self.pathRoot,
                                    "startTask" : self.lastTask,
                                    "endTask" : endTask,
                                    "totalTasks" : self.totalTasks,
                                    "numSubtasks" : self.numSubtasks,
                                    "numCores" : self.numCores,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFile" : os.path.relpath( self.sceneFile, commonPathPrefix )
                                }

        hash = "{}".format( random.getrandbits(128) )
        self.subTasksGiven[ hash ] = extraData
        self.lastTask = endTask # TODO: Should depend on performance

        ctd = ComputeTaskDef()
        ctd.taskId              = self.header.taskId
        ctd.subTaskId           = hash
        ctd.extraData           = extraData
        ctd.returnAddress       = self.header.taskOwnerAddress
        ctd.returnPort          = self.header.taskOwnerPort
        ctd.shortDescription    = self.__shortExtraDataRepr( perfIndex, extraData )
        ctd.srcCode             = self.srcCode
        ctd.performance         = perfIndex

        ctd.workingDirectory    = os.path.relpath( self.mainProgramFile, commonPathPrefix )
        ctd.workingDirectory    = os.path.dirname( ctd.workingDirectory )

        return ctd

    #######################
    def __shortExtraDataRepr( self, perfIndex, extraData ):
        l = extraData
        return "pathRoot: {}, startTask: {}, endTask: {}, totalTasks: {}, numSubtasks: {}, numCores: {}, outfilebasename: {}, sceneFile: {}".format( l["pathRoot"], l["startTask"], l["endTask"], l["totalTasks"], l["numSubtasks"], l["numCores"], l["outfilebasename"], l["sceneFile"] )

    #######################
    def needsComputation( self ):
        return self.lastTask != self.totalTasks

    #######################
    def computationStarted( self, extraData ):
        pass

    #######################
    def computationFinished( self, subTaskId, taskResult, env = None ):

        tmpDir = env.getTaskTemporaryDir( self.header.taskId )

        if len( taskResult ) > 0:
            for trp in taskResult:
                tr = pickle.loads( trp )
                fh = open( os.path.join( tmpDir, tr[ 0 ] ), "wb" )
                fh.write( decompress( tr[ 1 ] ) )
                fh.close()

                self.collector.acceptTask( os.path.join( tmpDir, tr[ 0 ] ) ) # pewnie tutaj trzeba czytac nie zpliku tylko z streama
                self.numTasksReceived += 1

            self.__updatePreview()

        if self.numTasksReceived == self.totalTasks:
            outputFileName = "{}.{}".format( self.outputFile, self.outputFormat )
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
            tmpDir = os.path.join( "res", self.header.clientId, self.header.taskId, "tmp" )

            if os.path.exists( dirName ):
                return prepareDeltaZip( dirName, resourceHeader, tmpDir, self.taskResources )
            else:
                return None
        else:
            return None

    #######################
    def __updatePreview( self ):

        tmpDir = os.path.join( "res", self.header.clientId, self.header.taskId, "tmp" )

        self.previewFilePath = "{}.{}".format( os.path.join( tmpDir, "current_preview") , "BMP" )

        self.collector.finalize().save( self.previewFilePath, "BMP" )

    #######################
    def getPreviewFilePath( self ):
        return self.previewFilePath