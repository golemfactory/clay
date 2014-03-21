#  MiniLight Python : minimal global illumination renderer
#
#  Harrison Ainsworth / HXA7241 and Juraj Sukop : 2007-2008, 2013.
#  http://www.hxa.name/minilight


from camera import Camera
from image import Image
from scene import Scene
from random import Random

from sys import argv, stdout
from time import time

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

if __name__ == '__main__':
    if len(argv) < 2 or argv[1] == '-?' or argv[1] == '--help':
        print HELP
    else:
        print BANNER
        random = Random()
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
