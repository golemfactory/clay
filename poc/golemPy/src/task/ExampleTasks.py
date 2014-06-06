
from TaskBase import Task, TaskHeader

from taskablerenderer import TaskableRenderer, RenderTaskResult, RenderTaskDesc
from Resource import prepareDeltaZip
from simplehash import SimpleHash

from takscollector import PbrtTaksCollector
import os
import cPickle as pickle

import random

from img import Img

testTaskScr2 = """ 
from minilight import render_task
from resource import ArrayResource
from base64 import encodestring

res = render_task( "d:/src/golem/poc/golemPy/testtasks/minilight/cornellbox.ml.txt", startX, startY, width, height, img_width, img_height )

output = encodestring( res )
"""


class RayTracingTask( Task ):
    #######################
    def __init__( self, width, height, taskHeader, returnAddress = "", returnPort = 0 ):
        coderes = testTaskScr2
        Task.__init__( self, taskHeader, [], coderes, 0 )
        self.width = width
        self.height = height
        self.splitIndex = 0
        self.returnAddress = returnAddress
        self.returnPort = returnPort

    #######################
    def queryExtraData( self, perfIndex ):
        hash = "{}".format( random.getrandbits(128) )
        return {    "startX" : 0,
                    "startY" : 0,
                    "width" : self.width,
                    "height" : self.height,
                    "img_width" : self.width,
                    "img_height" : self.height }, hash, self.returnAddress, self.returnPort

    #######################
    def shortExtraDataRepr( self, perfIndex ):
        return self.queryExtraData( perfIndex ).__str__()

    #######################
    def needsComputation( self ):
        if self.splitIndex < 1:
            return True
        else:
            return False

    #######################
    def computationStarted( self, extraData ):
        self.splitIndex += 1

    #######################
    def computationFinished( self, subTaskId, taskResult, env = None ):
        print "Receive computed task id:{} \n result:{}".format( self.taskHeader.taskId, taskResult )

TIMESLC  = 45.0
TIMEOUT  = 100000.0

task_data = u'''
(0.278 0.275 -0.789) (0 0 1) 40


(0.0906 0.0943 0.1151) (0.1 0.09 0.07)


(0.556 0.000 0.000) (0.006 0.000 0.559) (0.556 0.000 0.559)  (0.7 0.7 0.7) (0 0 0)
(0.006 0.000 0.559) (0.556 0.000 0.000) (0.003 0.000 0.000)  (0.7 0.7 0.7) (0 0 0)

(0.556 0.000 0.559) (0.000 0.549 0.559) (0.556 0.549 0.559)  (0.7 0.7 0.7) (0 0 0)
(0.000 0.549 0.559) (0.556 0.000 0.559) (0.006 0.000 0.559)  (0.7 0.7 0.7) (0 0 0)

(0.006 0.000 0.559) (0.000 0.549 0.000) (0.000 0.549 0.559)  (0.7 0.2 0.2) (0 0 0)
(0.000 0.549 0.000) (0.006 0.000 0.559) (0.003 0.000 0.000)  (0.7 0.2 0.2) (0 0 0)

(0.556 0.000 0.000) (0.556 0.549 0.559) (0.556 0.549 0.000)  (0.2 0.7 0.2) (0 0 0)
(0.556 0.549 0.559) (0.556 0.000 0.000) (0.556 0.000 0.559)  (0.2 0.7 0.2) (0 0 0)

(0.556 0.549 0.559) (0.000 0.549 0.000) (0.556 0.549 0.000)  (0.7 0.7 0.7) (0 0 0)
(0.000 0.549 0.000) (0.556 0.549 0.559) (0.000 0.549 0.559)  (0.7 0.7 0.7) (0 0 0)

(0.343 0.545 0.332) (0.213 0.545 0.227) (0.343 0.545 0.227)  (0.7 0.7 0.7) (1000 1000 1000)
(0.213 0.545 0.227) (0.343 0.545 0.332) (0.213 0.545 0.332)  (0.7 0.7 0.7) (1000 1000 1000)


(0.474 0.165 0.225) (0.426 0.165 0.065) (0.316 0.165 0.272)  (0.7 0.7 0.7) (0 0 0)
(0.266 0.165 0.114) (0.316 0.165 0.272) (0.426 0.165 0.065)  (0.7 0.7 0.7) (0 0 0)

(0.266 0.000 0.114) (0.266 0.165 0.114) (0.316 0.165 0.272)  (0.7 0.7 0.7) (0 0 0)
(0.316 0.000 0.272) (0.266 0.000 0.114) (0.316 0.165 0.272)  (0.7 0.7 0.7) (0 0 0)

(0.316 0.000 0.272) (0.316 0.165 0.272) (0.474 0.165 0.225)  (0.7 0.7 0.7) (0 0 0)
(0.474 0.165 0.225) (0.316 0.000 0.272) (0.474 0.000 0.225)  (0.7 0.7 0.7) (0 0 0)

(0.474 0.000 0.225) (0.474 0.165 0.225) (0.426 0.165 0.065)  (0.7 0.7 0.7) (0 0 0)
(0.426 0.165 0.065) (0.426 0.000 0.065) (0.474 0.000 0.225)  (0.7 0.7 0.7) (0 0 0)

(0.426 0.000 0.065) (0.426 0.165 0.065) (0.266 0.165 0.114)  (0.7 0.7 0.7) (0 0 0)
(0.266 0.165 0.114) (0.266 0.000 0.114) (0.426 0.000 0.065)  (0.7 0.7 0.7) (0 0 0)


(0.133 0.330 0.247) (0.291 0.330 0.296) (0.242 0.330 0.456)  (0.7 0.7 0.7) (0 0 0)
(0.242 0.330 0.456) (0.084 0.330 0.406) (0.133 0.330 0.247)  (0.7 0.7 0.7) (0 0 0)

(0.133 0.000 0.247) (0.133 0.330 0.247) (0.084 0.330 0.406)  (0.7 0.7 0.7) (0 0 0)
(0.084 0.330 0.406) (0.084 0.000 0.406) (0.133 0.000 0.247)  (0.7 0.7 0.7) (0 0 0)

(0.084 0.000 0.406) (0.084 0.330 0.406) (0.242 0.330 0.456)  (0.7 0.7 0.7) (0 0 0)
(0.242 0.330 0.456) (0.242 0.000 0.456) (0.084 0.000 0.406)  (0.7 0.7 0.7) (0 0 0)

(0.242 0.000 0.456) (0.242 0.330 0.456) (0.291 0.330 0.296)  (0.7 0.7 0.7) (0 0 0)
(0.291 0.330 0.296) (0.291 0.000 0.296) (0.242 0.000 0.456)  (0.7 0.7 0.7) (0 0 0)

(0.291 0.000 0.296) (0.291 0.330 0.296) (0.133 0.330 0.247)  (0.7 0.7 0.7) (0 0 0)
(0.133 0.330 0.247) (0.133 0.000 0.247) (0.291 0.000 0.296)  (0.7 0.7 0.7) (0 0 0)'''

class VRayTracingTask( Task ):
    #######################
    def __init__( self, width, height, num_samples, header, fileName, returnAddress = "", returnPort = 0 ):

        srcFile = open( "../testtasks/minilight/compact_src/renderer.py", "r")
        srcCode = srcFile.read()

        Task.__init__( self, header, srcCode )

        self.header.ttl = max( width * height * num_samples * 2 / 2200.0, TIMEOUT )

        self.taskableRenderer = None

        self.w = width
        self.h = height
        self.num_samples = num_samples

        self.lastExtraData = ""
        self.fileName = fileName
        self.returnAddress = returnAddress
        self.returnPort = returnPort

    #######################
    def __initRenderer( self ):
        self.taskableRenderer = TaskableRenderer( self.w, self.h, self.num_samples, None, TIMESLC, TIMEOUT )

    def initialize( self ):
        self.__initRenderer()

    #######################
    def queryExtraData( self, perfIndex ):

        taskDesc = self.taskableRenderer.getNextTaskDesc( perfIndex ) 

        self.lastExtraData =  {    "id" : taskDesc.getID(),
                    "x" : taskDesc.getX(),
                    "y" : taskDesc.getY(),
                    "w" : taskDesc.getW(),
                    "h" : taskDesc.getH(),
                    "num_pixels" : taskDesc.getNumPixels(),
                    "num_samples" : taskDesc.getNumSamples(),
                    "task_data" : task_data
                    }

        hash = "{}".format( random.getrandbits(128) )
        return self.lastExtraData, hash, self.returnAddress, self.returnPort

    #######################
    def shortExtraDataRepr( self, perfIndex ):
        if self.lastExtraData:
            l = self.lastExtraData
            return "x: {}, y: {}, w: {}, h: {}, num_pixels: {}, num_samples: {}".format( l["x"], l["y"], l["w"], l["h"], l["num_pixels"], l["num_samples"] )

        return ""

    #######################
    def needsComputation( self ):
        return self.taskableRenderer.hasMoreTasks()

    #######################
    def computationStarted( self, extraData ):
        pass

    #######################
    def computationFinished( self, subTaskId, taskResult, env = None ):
        #dest = RenderTaskDesc( 0, extraData[ "x" ], extraData[ "y" ], extraData[ "w" ], extraData[ "h" ], extraData[ "num_pixels" ] ,extraData[ "num_samples" ])
        #res = RenderTaskResult( dest, taskResult )
        #self.taskableRenderer.taskFinished( res )
        #if self.taskableRenderer.isFinished():
        #    VRayTracingTask.__save_image( self.fileName + ".ppm", self.w, self.h, self.taskableRenderer.getResult(), self.num_samples ) #FIXME: change file name here
        pass

    #######################
    def getTotalTasks( self ):
        return self.taskableRenderer.totalTasks

    #######################
    def getTotalChunks( self ):
        return self.taskableRenderer.pixelsCalculated

    #######################
    def getActiveTasks( self ):
        return self.taskableRenderer.activeTasks

    #######################
    def getActiveChunks( self ):
        return self.taskableRenderer.nextPixel - self.taskableRenderer.pixelsCalculated

    #######################
    def getChunksLeft( self ):
        return self.taskableRenderer.pixelsLeft

    #######################
    def getProgress( self ):
        return self.taskableRenderer.getProgress()

    #######################
    @classmethod
    def __save_image( cls, img_name, w, h, data, num_samples ):
        if not data:
            print "No data to write"
            return False

        img = Img( w, h )
        img.copyPixels( data )

        image_file = open( img_name, 'wb')
        img.get_formatted(image_file, num_samples)
        image_file.close()


from src.core.Compress import decompress

class PbrtRenderTask( Task ):

    #######################
    def __init__( self, header, pathRoot, totalTasks, numSubtasks, numCores, outfilebasename, sceneFile, returnAddress = "", returnPort = 0 ):

        srcFile = open( "../testtasks/pbrt/pbrt_compact.py", "r")
        srcCode = srcFile.read()

        Task.__init__( self, header, srcCode )

        self.header.ttl = max( 2200.0, TIMEOUT )

        self.pathRoot           = pathRoot
        self.lastTask           = 0
        self.totalTasks         = totalTasks
        self.numSubtasks        = numSubtasks
        self.numCores           = numCores
        self.outfilebasename    = outfilebasename
        self.sceneFile          = sceneFile

        self.lastExtraData      = None

        self.collector          = PbrtTaksCollector()
        self.numTasksReceived   = 0
        self.returnAddress      = returnAddress
        self.returnPort         = returnPort
        self.subTasksGiven      = {}

    def initialize( self ):
        pass

    #######################
    def queryExtraData( self, perfIndex ):

        endTask = min( self.lastTask + 1, self.totalTasks )

        self.lastExtraData =  {     "pathRoot" : self.pathRoot,
                                    "startTask" : self.lastTask,
                                    "endTask" : endTask,
                                    "totalTasks" : self.totalTasks,
                                    "numSubtasks" : self.numSubtasks,
                                    "numCores" : self.numCores,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFile" : self.sceneFile
                                }

        hash = "{}".format( random.getrandbits(128) )
        self.subTasksGiven[ hash ] = self.lastExtraData
        self.lastTask = endTask # TODO: Should depend on performance
        return self.lastExtraData, hash, self.returnAddress, self.returnPort

    #######################
    def shortExtraDataRepr( self, perfIndex ):
        if self.lastExtraData:
            l = self.lastExtraData
            return "pathRoot: {}, startTask: {}, endTask: {}, totalTasks: {}, numSubtasks: {}, numCores: {}, outfilebasename: {}, sceneFile: {}".format( l["pathRoot"], l["startTask"], l["endTask"], l["totalTasks"], l["numSubtasks"], l["numCores"], l["outfilebasename"], l["sceneFile"] )

        return ""

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
    def prepareResourceDelta( self, subTaskId, resourceHeader ):
        if subTaskId in self.subTasksGiven:
            dirName = os.path.join( "res", self.header.clientId, self.header.taskId, "resources" )
            tmpDir = os.path.join( "res", self.header.clientId, self.header.taskId, "tmp" )

            if os.path.exists( dirName ):
                return prepareDeltaZip( dirName, resourceHeader, tmpDir )
            else:
                return None
        else:
            return None