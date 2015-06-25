#  MiniLight Python : minimal global illumination renderer
#
#  Harrison Ainsworth / HXA7241 and Juraj Sukop : 2007-2008, 2013.
#  http://www.hxa.name/minilight


from math import log10
from vector3f import Vector3f

IMAGE_DIM_MAX = 4000
PPM_ID = 'P6'
MINILIGHT_URI = 'http://www.hxa.name/minilight'
DISPLAY_LUMINANCE_MAX = 200.0
RGB_LUMINANCE = Vector3f(0.2126, 0.7152, 0.0722)
GAMMA_ENCODE = 0.45

class Img(object):

    def __init__(self, w, h):
        self.width = w
        self.height = h
        self.pixels = [0.0] * self.width * self.height * 3

    def copyPixels(self, data):
        assert len(data) == len(self.pixels)

        i = 0
        for y in range(self.height):
            offset = 3 *(self.width * (self.height - 1 - y))
            for x in range(3 * self.width):
                self.pixels[ offset + x ] = data[ i ]
                i += 1

    def add_to_pixel(self, x, y, radiance):
        if x >= 0 and x < self.width and y >= 0 and y < self.height:
            index = (x + ((self.height - 1 - y) * self.width)) * 3
            for a in radiance:
                self.pixels[index] += a
                index += 1

    def get_formatted(self, out, iteration):
        divider = 1.0 / (iteration if iteration >= 1 else 1)
        tonemap_scaling = self.calculate_tone_mapping(self.pixels, divider)
        out.write('%s\n# %s\n\n%u %u\n255\n' % (PPM_ID, MINILIGHT_URI,
            self.width, self.height))
        for channel in self.pixels:
            mapped = channel * divider * tonemap_scaling
            gammaed = (mapped if mapped > 0.0 else 0.0) ** GAMMA_ENCODE
            out.write(chr(min(int((gammaed * 255.0) + 0.5), 255)))

    def calculate_tone_mapping(self, pixels, divider):
        sum_of_logs = 0.0
        for i in range(len(pixels) / 3):
            y = Vector3f(pixels[i * 3: i * 3 + 3]).dot(RGB_LUMINANCE) * divider
            sum_of_logs += log10(y if y > 1e-4 else 1e-4)
        adapt_luminance = 10.0 ** (sum_of_logs / (len(pixels) / 3))
        a = 1.219 + (DISPLAY_LUMINANCE_MAX * 0.25) ** 0.4
        b = 1.219 + adapt_luminance ** 0.4
        return ((a / b) ** 2.5) / DISPLAY_LUMINANCE_MAX
