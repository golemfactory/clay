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
        print "Receive cumputed task id:{} extraData:{} \n result:{}".format( self.taskHeader.id, extraData, taskResult )

TIMESLC  = 100.0
TIMEOUT  = 100000.0

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

    #######################
    def queryExtraData( self, perfIndex ):

        taskDesc = self.taskableRenderer.getNextTaskDesc( perfIndex ) 

        return {    "id" : taskDesc.getID(),
                    "x" : taskDesc.getX(),
                    "y" : taskDesc.getY(),
                    "w" : taskDesc.getW(),
                    "h" : taskDesc.getH(),
                    "num_pixels" : taskDesc.getNumPixels(),
                    "num_samples" : taskDesc.getNumSamples()
                    }

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
            VRayTracingTask.__save_image( "ladny.ppm", self.w, self.h, self.taskableRenderer.getResult(), self.num_samples )

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