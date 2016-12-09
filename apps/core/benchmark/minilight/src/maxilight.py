from camera import Camera
from image import Image
from scene import Scene

from mtrenderer import RenderWorker

from sys import argv
from time import time

BANNER = ''
HELP = '''
usage:
  minilight image_file_pathname
'''

MODEL_FORMAT_ID = '#MiniLight'

if __name__ == '__main__':

    def timedafunc(function):
    
        def timedExecution(*args, **kwargs):
            t0 = time()
            result = function (*args, **kwargs)
            t1 = time()

            return result, t1 - t0
            
        return timedExecution
 
    @timedafunc
    def render_taskable(image, image_file_pathname, camera, scene, num_samples, num_threads):
        workers = []
        
        for i in range(num_threads):
            worker = RenderWorker(camera, scene, image.width, image.height, i, num_threads, num_samples, image.accessRawPixelData())
            workers.append(worker)
            worker.start()
            
        totalRays = 0.0
        
        try:
            for w in workers:
                w.join()
            
        except KeyboardInterrupt:
            for w in workers:
                w.interrupt()
                w.join()
        finally:
            for w in workers:
                totalRays += w.progress() * image.width * image.height * num_samples / num_threads
            
        image_file = open(image_file_pathname, 'wb')
        image.get_formatted(image_file, num_samples)
        image_file.close()

        return totalRays

    def main():
        if len(argv) < 2 or argv[1] == '-?' or argv[1] == '--help':
            print HELP
        else:
            print BANNER
            model_file_pathname = argv[1]
            image_file_pathname = model_file_pathname + '.ppm'
            model_file = open(model_file_pathname, 'r')
            if model_file.next().strip() != MODEL_FORMAT_ID:
                raise 'invalid model file'
            for line in model_file:
                if not line.isspace():
                    iterations = int(line)
                    break
            image = Image(model_file)
            camera = Camera(model_file)
            scene = Scene(model_file, camera.view_position)
            model_file.close()

            numSamples, duration = render_taskable(image, image_file_pathname, camera, scene, iterations, 4)
            totalSamples = image.width * image.height * iterations
            avgSpeed = float(numSamples) / duration
            expectedTime = totalSamples / avgSpeed

            print "\nSummary:"
            print "    Rendering scene with {} rays took {} seconds".format(numSamples, duration)
            print "    giving an average speed of {} rays/s".format(avgSpeed)
            print "    estimated time for the whole scene is {} seconds".format(expectedTime)
            
    main()
