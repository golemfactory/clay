# Original file, modified by Golem Team:
#  MiniLight Python : minimal global illumination renderer
#
#  Harrison Ainsworth / HXA7241 and Juraj Sukop : 2007-2008, 2013.
#  http://www.hxa.name/minilight


import multiprocessing
from sys import argv, stdout
from time import time
import sys

sys.path.append("src")
from camera import Camera
from image import Image
from scene import Scene
from randommini import Random


BANNER = '''
  MiniLight 1.6 Python - http://www.hxa.name/minilight
'''
HELP = '''
----------------------------------------------------------------------
  MiniLight 1.6 Python

  Harrison Ainsworth / HXA7241 and Juraj Sukop : 2007-2008, 2013.
  http://www.hxa.name/minilight

  2013-05-04
----------------------------------------------------------------------

MiniLight is a minimal global illumination renderer.

usage:
  minilight image_file_pathname

The model text file format is:
  #MiniLight

  iterations

  imagewidth imageheight
  viewposition viewdirection viewangle

  skyemission groundreflection

  vertex0 vertex1 vertex2 reflectivity emitivity
  vertex0 vertex1 vertex2 reflectivity emitivity
  ...

- where iterations and image values are integers, viewangle is a real,
and all other values are three parenthised reals. The file must end
with a newline. E.g.:
  #MiniLight

  100

  200 150
  (0 0.75 -2) (0 0 1) 45

  (3626 5572 5802) (0.1 0.09 0.07)

  (0 0 0) (0 1 0) (1 1 0)  (0.7 0.7 0.7) (0 0 0)
'''
MODEL_FORMAT_ID = '#MiniLight'

def makePerfTest(filename, cfg_filename, num_cores):
    model_file_pathname = filename
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

    #render_orig(image, image_file_pathname, camera, scene, iterations)
    duration = render_taskable(image, image_file_pathname, camera, scene, iterations)

    numSamples = image.width * image.height * iterations
    print "\nSummary:"
    print "    Rendering scene with {} rays took {} seconds".format(numSamples, duration)
    print "    giving an average speed of {} rays/s".format(float(numSamples) / duration)
    cfg_file = open(cfg_filename, 'w')
    average = float(numSamples) / duration
    average = average * num_cores
    cfg_file.write("{0:.1f}".format(average))
    cfg_file.close()
    return average

def timedafunc(function):

    def timedExecution(*args, **kwargs):
        t0 = time()
        result = function (*args, **kwargs)
        t1 = time()

        return t1 - t0

    return timedExecution

def render_orig(image, image_file_pathname, camera, scene, iterations):
    random = Random()

    try:
        for frame_no in range(1, iterations + 1):
            stdout.write('\riteration: %u' % frame_no)
            stdout.flush()
            camera.get_frame(scene, random, image)
            if ((frame_no & (frame_no -1)) == 0) or frame_no == iterations:
                image_file = open(image_file_pathname, 'wb')
                image.get_formatted(image_file, frame_no)
                image_file.close()
        print '\nfinished'
    except KeyboardInterrupt:
        print '\ninterrupted'

@timedafunc
def render_taskable(image, image_file_pathname, camera, scene, num_samples):
    random = Random()
    aspect = float(image.height) / float(image.width)
    samplesPerUpdate = 200

    try:
        totalPasses = float(image.height * image.width)
        curPass = 0
        passUpdateDelta = samplesPerUpdate // num_samples if  num_samples < samplesPerUpdate else 1

        for y in range(image.height):
            for x in range(image.width):
                #separated tasks which should be added to the final image when they are ready (even better simple pixel values can be accumulated simply via additions and num iterations just
                #has to be passed to tone mapper)
                r = camera.pixel_accumulated_radiance(scene, random, image.width, image.height, x, y, aspect, num_samples)

                #accumulation of stored values (can be easily moved to a separate loop over x and y (and the results from radiance calculations)
                image.add_to_pixel(x, y, r)

                curPass += 1

                if curPass % passUpdateDelta == 0:
                    stdout.write('\r                                          ')
                    stdout.write('\rProgress: {} %'.format(float(curPass) * 100.0 / totalPasses))
                    stdout.flush()

        # image_file = open(image_file_pathname, 'wb')
        # image.get_formatted(image_file, num_samples)
        # image_file.close()

        print '\nfinished'
    except KeyboardInterrupt:
        print '\ninterrupted'



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

        #render_orig(image, image_file_pathname, camera, scene, iterations)
        duration = render_taskable(image, image_file_pathname, camera, scene, iterations)

        numSamples = image.width * image.height * iterations
        print "\nSummary:"
        print "    Rendering scene with {} rays took {} seconds".format(numSamples, duration)
        print "    giving an average speed of {} rays/s".format(float(numSamples) / duration)
        cfg_file = open('minilight.ini', 'w')
        average = float(numSamples) / duration
        average = average * multiprocessing.cpu_count()
        cfg_file.write("{0:.1f}".format(average))
        cfg_file.close()


if __name__ == "__main__":
    main()