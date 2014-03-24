from threading import Thread, current_thread
from raytracer import RayTracer
from random import Random
from math import pi, tan
from vector3f import Vector3f


class RenderWorker(Thread):
    
    def __init__( self, camera, scene, width, height, id, step, num_samples, pixelData ):
        Thread.__init__( self )
        self.cam = camera
        self.w = width
        self.h = height
        self.i = id
        self.dp = step
        self.ns = num_samples
        self.data = pixelData
        self.aspect = float(height) / float(width)
        self.quit = False
        self.rnd = Random()
        self.curPass = 0;
        self.rtcr = RayTracer(scene)

    def interrupt( self ):
        self.quit = True

    def progress( self ):
        cp = float( self.curPass )
        total = float( self.w * self.h ) / float( self.dp )

        return float( cp ) / float( total )

    def radiance( self, x, y ):
        r = 0.0
        g = 0.0
        b = 0.0
        for i in range( self.ns ):
            x_coefficient = ((x + self.rnd.real64()) * 2.0 / self.w) - 1.0
            y_coefficient = ((y + self.rnd.real64()) * 2.0 / self.h) - 1.0
            offset = self.cam.right * x_coefficient + self.cam.up * (y_coefficient * self.aspect)
            sample_direction = (self.cam.view_direction + (offset * tan(self.cam.view_angle * 0.5))).unitize()

            rnc = self.rtcr.get_radiance(self.cam.view_position,sample_direction, self.rnd)
        
            r += rnc[ 0 ]
            g += rnc[ 1 ]
            b += rnc[ 2 ]
            
        return Vector3f( r, g, b )

    def getXY( self, idx ):
        return idx % self.w, idx // self.w

    def writePixel( self, x, y, col ):
        idx = (x + ((self.h - 1 - y) * self.w)) * 3

        self.data[ idx + 0 ] = col[ 0 ]
        self.data[ idx + 1 ] = col[ 1 ]
        self.data[ idx + 2 ] = col[ 2 ]

    def run(self):
        for i in range( self.i, self.w * self.h, self.dp ):
            x, y = self.getXY( i )            
            r = self.radiance( x, y )
            self.writePixel( x, y, r )
            
            self.curPass += 1
            
            if self.quit:
                print "Forced quit"
                break

        print "{} finished renbdering".format( current_thread() )
