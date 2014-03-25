#  MiniLight Python : minimal global illumination renderer
#
#  Harrison Ainsworth / HXA7241 and Juraj Sukop : 2007-2008, 2013.
#  http://www.hxa.name/minilight


from camera import Camera
from image import Image
from scene import Scene
from randommini import Random
from vector3f import Vector3f
from math import log10

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

class Rect:
	def __init__( self, x, y, width, height ):
		self.x 		= x
		self.y 		= y
		self.width 	= width
		self.height = height

def render_task( sceneFile, x, y, width, height, img_width, img_height ):
    print BANNER
    model_file_pathname = sceneFile
    model_file = open(model_file_pathname, 'r')
    if model_file.next().strip() != MODEL_FORMAT_ID:
        raise 'invalid model file'
    for line in model_file:
        if not line.isspace():
            iterations = int(line)
            break
    #image = Image(model_file)
    camera = Camera(model_file)
    scene = Scene(model_file, camera.view_position)
    model_file.close()
    
    res = render_rect( Rect(x, y, width, height), img_width, img_height, camera, scene, iterations )
    # totalSamples = image.width * image.height * iterations
    # avgSpeed = float( numSamples ) / duration
    # expectedTime = totalSamples / avgSpeed

    # print "\nSummary:"
    # print "    Rendering scene with {} rays took {} seconds".format( numSamples, duration )
    # print "    giving an average speed of {} rays/s".format( avgSpeed )
    # print "    estimated time for the whole scene is {} seconds".format( expectedTime )
    return res

def timedafunc( function ):

    def timedExecution(*args, **kwargs):
        t0 = time()
        result = function ( *args, **kwargs )
        t1 = time()

        return result, t1 - t0
        
    return timedExecution

def render_orig( image, image_file_pathname, camera, scene, iterations ): 
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
def render_taskable( image, image_file_pathname, camera, scene, num_samples ):
    random = Random()
    aspect = float(image.height) / float(image.width)
    samplesPerUpdate = 2000
    
    print camera

    curPass = 0
    try:
        totalPasses = float( image.height * image.width )
        passUpdateDelta = samplesPerUpdate // num_samples if  num_samples < samplesPerUpdate else 1
        
        for y in range(image.height):
            for x in range(image.width):
                #separated tasks which should be added to the final image when they are ready (even better simple pixel values can be accumulated simply via additions and num iterations just 
                #has to be passed to tone mapper)
                r = camera.pixel_accumulated_radiance(scene, random, image, x, y, aspect, num_samples)
                
                #accumulation of stored values (can be easily moved to a separate loop over x and y (and the results from radiance calculations) 
                image.add_to_pixel( x, y, r )
                
                curPass += 1

                if curPass % passUpdateDelta == 0:
                    stdout.write('\r                                          ')
                    stdout.write('\rProgress: {} %'.format( float( curPass ) * 100.0 / totalPasses ) )
                    stdout.flush()
                    
        image_file = open(image_file_pathname, 'wb')
        image.get_formatted(image_file, num_samples)
        image_file.close()

        print '\nfinished'
    except KeyboardInterrupt:
        print '\ninterrupted'
    
    return curPass * num_samples


def render_rect( rect, img_width, img_height, camera, scene, num_samples ):
    assert isinstance( rect, Rect )
    aspect = float(img_height) / float(img_width)
    random = Random()
    samplesPerUpdate = 2000
    
    out = [ 0.0 ] * rect.width * rect.height * 3
    
    curPass = 0
    try:
        totalPasses = float( rect.width * rect.height )
        passUpdateDelta = samplesPerUpdate // num_samples if  num_samples < samplesPerUpdate else 1
        
        for y in range(rect.y, rect.y + rect.height):
            for x in range(rect.x, rect.x + rect.width):
                radiance = camera.pixel_accumulated_radiance(scene, random, img_width, img_height, x, y, aspect, num_samples)
                  
                absX = x - rect.x             
                absY = y - rect.y             
                if absX >= 0 and absX < rect.width and absY >= 0 and absY < rect.height:
                    index = (absX + ((rect.height - 1 - absY) * rect.width)) * 3
                    for a in radiance:
                        out[index] += a
                        index += 1
                
                curPass += 1

                if curPass:
                    #stdout.write('\r                                          ')
                    stdout.write('\rProgress: {} % \n'.format( float( curPass ) * 100.0 / totalPasses ) )
                    stdout.flush()
        print '\nfinished'
    except KeyboardInterrupt:
        print '\ninterrupted'  

    print out
    return get_formatted( out, num_samples )
   
IMAGE_DIM_MAX = 4000
PPM_ID = 'P6'
MINILIGHT_URI = 'http://www.hxa.name/minilight'
DISPLAY_LUMINANCE_MAX = 200.0
RGB_LUMINANCE = Vector3f(0.2126, 0.7152, 0.0722)
GAMMA_ENCODE = 0.45

def get_formatted(pixels, iteration):
    divider = 1.0 / (iteration if iteration >= 1 else 1)
    tonemap_scaling = calculate_tone_mapping(pixels, divider)
    out = bytearray()
    for channel in pixels:
        mapped = channel * divider * tonemap_scaling
        gammaed = (mapped if mapped > 0.0 else 0.0) ** GAMMA_ENCODE
        out.append(chr(min(int((gammaed * 255.0) + 0.5), 255)))

    return out

def calculate_tone_mapping(pixels, divider):
    sum_of_logs = 0.0
    for i in range(len(pixels) / 3):
        y = Vector3f(pixels[i * 3: i * 3 + 3]).dot(RGB_LUMINANCE) * divider
        sum_of_logs += log10(y if y > 1e-4 else 1e-4)
    adapt_luminance = 10.0 ** (sum_of_logs / (len(pixels) / 3))
    a = 1.219 + (DISPLAY_LUMINANCE_MAX * 0.25) ** 0.4
    b = 1.219 + adapt_luminance ** 0.4
    return ((a / b) ** 2.5) / DISPLAY_LUMINANCE_MAX  

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
       
       print camera
       return
       scene = Scene(model_file, camera.view_position)
       model_file.close()
        
       #render_orig( image, image_file_pathname, camera, scene, iterations )
       #numSamples, duration = render_taskable( image, image_file_pathname, camera, scene, iterations )
       #numSamples, duration = render_rect( Rect(0, 0, 50, 1), image.width, image.height, camera, scene, iterations )
       numSamples, duration = render_rect( Rect(0, 0, image.width, image.height), image.width, image.height, camera, scene, iterations )
       totalSamples = image.width * image.height * iterations
       avgSpeed = float( numSamples ) / duration
       expectedTime = totalSamples / avgSpeed

       print "\nSummary:"
       print "    Rendering scene with {} rays took {} seconds".format( numSamples, duration )
       print "    giving an average speed of {} rays/s".format( avgSpeed )
       print "    estimated time for the whole scene is {} seconds".format( expectedTime )
        
main()
