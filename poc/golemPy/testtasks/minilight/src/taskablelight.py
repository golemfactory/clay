from taskablerenderer import TaskableRenderer
from renderworker import RenderWorker
from img import Img

import task_data_0

if __name__ == "__main__":

    def save_image( img_name, w, h, data, num_samples ):
        if not data:
            print "No data to write"
            return False

        img = Img( w, h )
        img.copyPixels( data )

        image_file = open( img_name, 'wb')
        img.get_formatted(image_file, num_samples)
        image_file.close()

    w   = 30
    h   = 30
    ns  = 20
    sd  = task_data_0.deserialized_task
    pts = 6.0
    timeout = 3600.0
    img_name = "image_of_the_task.ppm"

    tr = TaskableRenderer( w, h, ns, sd, pts, timeout )
    tr.start()

    while not tr.isFinished():
        task = tr.getNextTask( 1620.0 )
        rw = RenderWorker( task )
        #tr.printStats()
        rw.render()
        #tr.printStats()

    tr.printStats()

    print "Writing result image {}".format( img_name )
    save_image( img_name, w, h, tr.getResult(), ns )

#from sys import argv, stdout
#from time import time
#from io import StringIO
#from math import pi, tan

#from camera import Camera
#from img import Img
#from scene import Scene
#from raytracer import RayTracer
#from vector3f import Vector3f
#from randommini import Random

#import task_data_0

#if __name__ == "__main__":

#    w = 20
#    h = 20
#    num_samples = 40

#    rw = RenderWorker.createWorker( 0, 0, w, h, w * h, num_samples, task_data_0.deserialized_task )
#    data = rw.render()

#    img = Img( w, h )
#    img.copyPixels( data )

#    image_file = open( "temp_file.ppm", 'wb')
#    img.get_formatted(image_file, num_samples)
#    image_file.close()

#    def some_shit():
#        import sys

#        rn = Random()
    
#        print "Preallocating"

#        ilo = [0.0] * 1024 * 1024 * 10
#        rdn = []
    
#        print "Pregenerating"

#        for k in range( 1024 // 32 ):
#            rdn.append( rn.real64() )

#        print "Starting adding"

#        z = 0
#        for k in range( 1024 // 32 ):
#            print "\rElt {}".format( k ),
#            for i in range( 1024 * 10 * 32 ):
#                ilo[ z ] = rdn[ k ]
#                z += 1

#        z = 0
#        print "Starting printing"
#        for k in range( 1024 // 32 ):
#            sum = 0.0
#            for i in range( 1024 * 10 * 32 ):
#                sum += ilo[ z ]
#                z += 1
#            print "\rPresummer {:02} {}".format( k, sum )

#        sys.exit( 0 )

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
