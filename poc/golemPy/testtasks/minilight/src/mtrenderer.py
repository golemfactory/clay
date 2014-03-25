from multiprocessing import Process, Array
from raytracer import RayTracer
from randommini import Random
from math import pi, tan
from vector3f import Vector3f


def render( self, camera, scene, w, h, xs, ys, num_pixels, num_samples, pixels ):
        
    def progress( cp, w, h, step ):
        return float( w * h ) / float( step )

    def radiance( x, y, w, h, rnd, cam, aspect, rctr, ns ):
        r = 0.0
        g = 0.0
        b = 0.0
        for i in range( ns ):
            x_coefficient = ((x + rnd.real64()) * 2.0 / w) - 1.0
            y_coefficient = ((y + rnd.real64()) * 2.0 / h) - 1.0
            offset = cam.right * x_coefficient + cam.up * (y_coefficient * aspect)
            sample_direction = (cam.view_direction + (offset * tan(cam.view_angle * 0.5))).unitize()

            rnc = rtcr.get_radiance(cam.view_position,sample_direction, rnd)

            r += rnc[ 0 ]
            g += rnc[ 1 ]
            b += rnc[ 2 ]
            
        return Vector3f( r, g, b )

    def getXY( i, w, h ):
        return i % w, i // w
        
    def writePixel( x, y, pixels, col ):
        idx = (x + ((self.h - 1 - y) * self.w)) * 3

        self.data[ idx + 0 ] = col[ 0 ]
        self.data[ idx + 1 ] = col[ 1 ]
        self.data[ idx + 2 ] = col[ 2 ]

    aspect = float( h ) / float( w )
    raytracer = RayTracer( scene )
    rnd = Random()

    k = 0
    for i in range ( y * w + x, w * h ):
        x, y = getXY( i, w, h )
        r = radiance( x, y, w, h, rnd, camera, aspect, raytracer, num_samples )
        
        pixels[ k + 0 ] = r[ 0 ]
        pixels[ k + 1 ] = r[ 1 ]
        pixels[ k + 2 ] = r[ 2 ]

        k += 3
