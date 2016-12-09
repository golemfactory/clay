#  MiniLight Python : minimal global illumination renderer
#
#  Harrison Ainsworth / HXA7241 and Juraj Sukop : 2007-2008, 2013.
#  http://www.hxa.name/minilight


from spatialindex import SpatialIndex
from triangle import Triangle
from vector3f import Vector3f, ZERO, ONE, MAX

import re
SEARCH = re.compile('(\(.+\))\s*(\(.+\))').search

MAX_TRIANGLES = 0x1000000

class Scene(object):

    def __init__(self, in_stream, eye_position):
        for l in in_stream:
            if type(l) == type(u""):
                line = l.encode('ascii','ignore')
            else:
                line = l
            if not line.isspace():
                s, g = SEARCH(line).groups()
                self.sky_emission = Vector3f(s).clamped(ZERO, MAX)
                self.ground_reflection = Vector3f(g).clamped(ZERO, ONE)
                self.triangles = []
                try:
                    for i in range(MAX_TRIANGLES):
                        self.triangles.append(Triangle(in_stream))
                except StopIteration:
                    pass
                self.emitters = [triangle for triangle in self.triangles
                    if not triangle.emitivity.is_zero() and triangle.area > 0.0]
                self.index = SpatialIndex(eye_position, self.triangles)
                self.get_intersection = self.index.get_intersection
                break

    ##def get_intersection(self, ray_origin, ray_direction, last_hit):
    ##    return self.index.get_intersection(ray_origin, ray_direction,
    ##        last_hit)

    def get_emitter(self, random):
        emitter = None if len(self.emitters) == 0 else self.emitters[
            min(len(self.emitters) - 1,
                int(random.real64() * len(self.emitters))) ]
        return [(emitter.get_sample_point(random) if emitter else ZERO),
            emitter]

    def emitters_count(self):
        return len(self.emitters)

    def get_default_emission(self, back_direction):
        return self.sky_emission if back_direction.y < 0.0 else \
            self.sky_emission * self.ground_reflection
