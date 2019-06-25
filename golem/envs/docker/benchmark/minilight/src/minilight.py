# Original file, modified by Golem Team:
#  MiniLight Python : minimal global illumination renderer
#
#  Harrison Ainsworth / HXA7241 and Juraj Sukop : 2007-2008, 2013.
#  http://www.hxa.name/minilight
import logging
from time import time

from .camera import Camera
from .image import Image
from .scene import Scene
from .randommini import Random

MODEL_FORMAT_ID = '#MiniLight'

logger = logging.getLogger(__name__)


def make_perf_test(filename):
    """
    Single core CPU performance test.

    ----------------------------------------------------------------------
      MiniLight 1.6 Python

      Harrison Ainsworth / HXA7241 and Juraj Sukop : 2007-2008, 2013.
      http://www.hxa.name/minilight

      2013-05-04
    ----------------------------------------------------------------------

    MiniLight is a minimal global illumination renderer.

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
    """
    model_file_pathname = filename
    model_file = open(model_file_pathname, 'r')
    if model_file.readline().strip() != MODEL_FORMAT_ID:
        raise Exception('invalid model file')
    for line in model_file:
        if not line.isspace():
            iterations = int(line)
            break
    image = Image(model_file)
    camera = Camera(model_file)
    scene = Scene(model_file, camera.view_position)
    model_file.close()

    duration: float = render_taskable(image, camera, scene, iterations)

    num_samples = image.width * image.height * iterations
    logger.debug("Summary: Rendering scene with %d rays took %d seconds"
                 " giving an average speed of %f rays/s",
                 num_samples, duration, float(num_samples) / duration)

    average = float(num_samples) / duration
    return average


def timedafunc(function):
    def timedExecution(*args, **kwargs):
        t0 = time()
        function(*args, **kwargs)
        t1 = time()

        return t1 - t0

    return timedExecution


@timedafunc
def render_taskable(image, camera, scene, num_samples):
    random = Random()
    aspect = float(image.height) / float(image.width)

    for y in range(image.height):
        for x in range(image.width):
            # separated tasks which should be added to the final image when they
            # are ready (even better simple pixel values can be accumulated
            # simply via additions and num iterations just has to be passed to
            # tone mapper)
            r = camera.pixel_accumulated_radiance(
                scene, random, image.width, image.height, x, y, aspect,
                num_samples)

            # accumulation of stored values (can be easily moved to a separate
            # loop over x and y (and the results from radiance calculations)
            image.add_to_pixel(x, y, r)
