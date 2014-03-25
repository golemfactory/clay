from sys import argv, stdout
from time import time
from io import StringIO
from math import pi, tan

from camera import Camera
from img import Img
from scene import Scene
from raytracer import RayTracer
from vector3f import Vector3f
from randommini import Random

import task_data_0

class RenderWorker:

    @classmethod
    def createWorker( cls, x, y, w, h, num_pixels, num_samples, scene_data ):
        if x >= w or y >= h or num_samples < 1:
            return None

        totalPixels = w * h
        leftOver = totalPixels - h * y + x

        if leftOver < num_pixels < 1:
            return None

        data_stream = StringIO( scene_data )

        camera  = Camera( data_stream )
        scene   = Scene( data_stream, camera.view_position )

        return RenderWorker( x, y, w, h, num_pixels, num_samples, camera, scene )

    def __init__( self, x, y, w, h, num_pixels, num_samples, camera, scene ):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.aspect = float( h ) / float( w )
        
        self.num_pixels = num_pixels
        self.num_samples = num_samples

        self.camera = camera
        self.scene = scene
        self.raytracer = RayTracer(scene)

        self.random = Random()

        self.progress = 0.0

    def getProgress( self ):
        return self.progress

    def sample_radiance( self, x, y ):
        acc_radiance = [ 0.0, 0.0, 0.0 ]

        for i in range(self.num_samples):
            x_coefficient = ((x + self.random.real64()) * 2.0 / self.w) - 1.0
            y_coefficient = ((y + self.random.real64()) * 2.0 / self.h) - 1.0

            offset = self.camera.right * x_coefficient + self.camera.up * (y_coefficient * self.aspect)

            sample_direction = (self.camera.view_direction + (offset * tan(self.camera.view_angle * 0.5))).unitize()

            radiance = self.raytracer.get_radiance(self.camera.view_position,sample_direction, self.random)

            acc_radiance[ 0 ] += radiance[ 0 ]          
            acc_radiance[ 1 ] += radiance[ 1 ]          
            acc_radiance[ 2 ] += radiance[ 2 ]          				
        
        return Vector3f( acc_radiance[ 0 ], acc_radiance[ 1 ], acc_radiance[ 2 ] )

    def getXY( self, idx ):
        return idx % self.w, idx // self.w

    def render( self ):
        pixels = [0.0] * 3 * self.num_pixels
        offset  = self .y * self.w + self.x

        for k in range( self.num_pixels ):
            x, y = self.getXY( k + offset )
            radiance = self.sample_radiance( x, y )

            pixels[ 3 * k + 0 ] = radiance[ 0 ]                
            pixels[ 3 * k + 1 ] = radiance[ 1 ]                
            pixels[ 3 * k + 2 ] = radiance[ 2 ]                
        
        return pixels

if __name__ == "__main__":

    w = 20
    h = 20
    num_samples = 40

    rw = RenderWorker.createWorker( 0, 0, w, h, w * h, num_samples, task_data_0.deserialized_task )
    data = rw.render()

    img = Img( w, h )
    img.copyPixels( data )

    image_file = open( "temp_file.ppm", 'wb')
    img.get_formatted(image_file, num_samples)
    image_file.close()
#        return RenderWorker( x, y, w, h, num_pixels, num_samples, sce

#    def __init__( self, x, y, w, h, 

#def renderPixels( 
#BANNER = ''
#HELP = '''
#usage:
#  minilight image_file_pathname
#'''

#MODEL_FORMAT_ID = '#MiniLight'

#if __name__ == '__main__':

#    def timedafunc( function ):
    
#        def timedExecution(*args, **kwargs):
#            t0 = time()
#            result = function ( *args, **kwargs )
#            t1 = time()

#            return result, t1 - t0
            
#        return timedExecution
 
#    @timedafunc
#    def render_taskable( image, image_file_pathname, camera, scene, num_samples, num_threads ):
#        workers = []
        
#        for i in range( num_threads ):
#            worker = RenderWorker( camera, scene, image.width, image.height, i, num_threads, num_samples, image.accessRawPixelData() )
#            workers.append( worker )
#            worker.start()
            
#        totalRays = 0.0
        
#        try:
#            for w in workers:
#                w.join()
            
#        except KeyboardInterrupt:
#            for w in workers:
#                w.interrupt()
#                w.join()
#        finally:
#            for w in workers:
#                totalRays += w.progress() * image.width * image.height * num_samples / num_threads
            
#        image_file = open(image_file_pathname, 'wb')
#        image.get_formatted(image_file, num_samples)
#        image_file.close()

#        return totalRays

#    def main():
#        if len(argv) < 2 or argv[1] == '-?' or argv[1] == '--help':
#            print HELP
#        else:
#            print BANNER
#            model_file_pathname = argv[1]
#            image_file_pathname = model_file_pathname + '.ppm'
#            model_file = open(model_file_pathname, 'r')
#            if model_file.next().strip() != MODEL_FORMAT_ID:
#                raise 'invalid model file'
#            for line in model_file:
#                if not line.isspace():
#                    iterations = int(line)
#                    break
#            image = Image(model_file)
#            camera = Camera(model_file)
#            scene = Scene(model_file, camera.view_position)
#            model_file.close()

#            numSamples, duration = render_taskable( image, image_file_pathname, camera, scene, iterations, 4 )
#            totalSamples = image.width * image.height * iterations
#            avgSpeed = float( numSamples ) / duration
#            expectedTime = totalSamples / avgSpeed

#            print "\nSummary:"
#            print "    Rendering scene with {} rays took {} seconds".format( numSamples, duration )
#            print "    giving an average speed of {} rays/s".format( avgSpeed )
#            print "    estimated time for the whole scene is {} seconds".format( expectedTime )
            
#    main()
