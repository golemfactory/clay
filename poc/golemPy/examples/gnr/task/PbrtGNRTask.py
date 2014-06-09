import os
import random
import cPickle as pickle

from golem.task.TaskBase import TaskBuilder, ComputeTaskDef
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
                                   self.taskDefinition.resources )

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

        self.collector          = PbrtTaksCollector()
        self.numTasksReceived   = 0
        self.subTasksGiven      = {}


    def initialize( self ):
        pass

    #######################
    def queryExtraData( self, perfIndex ):

        endTask = min( self.lastTask + 1, self.totalTasks )

        extraData =          {      "pathRoot" : self.pathRoot,
                                    "startTask" : self.lastTask,
                                    "endTask" : endTask,
                                    "totalTasks" : self.totalTasks,
                                    "numSubtasks" : self.numSubtasks,
                                    "numCores" : self.numCores,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFile" : self.sceneFile
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


        if self.numTasksReceived == self.totalTasks:
            self.collector.finalize().save( "{}.png".format( os.path.join( env.getTaskOutputDir( self.header.taskId ), "test" ) ), "PNG" )

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
    def prepareResourceDelta( self, subTaskId, taskId, resourceHeader ):
        if taskId == self.header.taskId:
            dirName = os.path.join( "res", self.header.clientId, self.header.taskId, "resources" )
            tmpDir = os.path.join( "res", self.header.clientId, self.header.taskId, "tmp" )

            if os.path.exists( dirName ):
                return prepareDeltaZip( dirName, resourceHeader, tmpDir )
            else:
                return None
        else:
            return None

