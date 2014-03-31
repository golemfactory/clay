from taskbase import Task, TaskHeader

from taskablerenderer import TaskableRenderer, RenderTaskResult, RenderTaskDesc

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
    def __init__( self, width, height, taskHeader ):
        coderes = testTaskScr2
        Task.__init__( self, taskHeader, [], coderes, 0 )
        self.width = width
        self.height = height
        self.splitIndex = 0

    #######################
    def queryExtraData( self, perfIndex ):
        return {    "startX" : 0,
                    "startY" : 0,
                    "width" : self.width,
                    "height" : self.height,
                    "img_width" : self.width,
                    "img_height" : self.height }

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
    def computationFinished( self, extraData, taskResult ):
        print "Receive computed task id:{} extraData:{} \n result:{}".format( self.taskHeader.id, extraData, taskResult )

TIMESLC  = 100.0
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
    def __init__( self, width, height, num_samples, header ):

        srcFile = open( "../testtasks/minilight/compact_src/renderer.py", "r")
        srcCode = srcFile.read()

        Task.__init__( self, header, srcCode )

        self.header.ttl = max( width * height * num_samples * 2 / 1200.0, TIMEOUT )

        self.taskableRenderer = TaskableRenderer( width, height, num_samples, None, TIMESLC, TIMEOUT )

        self.w = width
        self.h = height
        self.num_samples = num_samples

        self.lastExtraData = ""

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

        return self.lastExtraData

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
    def computationFinished( self, extraData, taskResult ):
        dest = RenderTaskDesc( 0, extraData[ "x" ], extraData[ "y" ], extraData[ "w" ], extraData[ "h" ], extraData[ "num_pixels" ] ,extraData[ "num_samples" ])
        res = RenderTaskResult( dest, taskResult )
        self.taskableRenderer.taskFinished( res )
        if self.taskableRenderer.isFinished():
            VRayTracingTask.__save_image( "ladny.ppm", self.w, self.h, self.taskableRenderer.getResult(), self.num_samples ) #FIXME: change file name here

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