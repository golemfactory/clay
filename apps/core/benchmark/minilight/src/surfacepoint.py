#  MiniLight Python : minimal global illumination renderer
#
#  Harrison Ainsworth / HXA7241 and Juraj Sukop : 2007-2008, 2013.
#  http://www.hxa.name/minilight


from math import cos, pi, sin, sqrt
from vector3f import Vector3f, ONE, ZERO

class SurfacePoint(object):

    def __init__(self, triangle, position):
        self.triangle_ref = triangle
        self.position = Vector3f(position)

    def get_emission(self, to_position, out_direction, is_solid_angle):
        ray = to_position - self.position
        distance2 = ray.dot(ray)
        cos_area = out_direction.dot(self.triangle_ref.normal) * \
            self.triangle_ref.area
        solid_angle = cos_area / max(distance2, 1e-6) if is_solid_angle else 1.0
        return self.triangle_ref.emitivity * solid_angle \
            if cos_area > 0.0 else ZERO

    def get_reflection(self, in_direction, in_radiance, out_direction):
        in_dot = in_direction.dot(self.triangle_ref.normal)
        out_dot = out_direction.dot(self.triangle_ref.normal)
        return ZERO if (in_dot < 0.0) ^ (out_dot < 0.0) else \
            in_radiance * self.triangle_ref.reflectivity * (abs(in_dot) / pi)

    def get_next_direction(self, random, in_direction):
        reflectivity_mean = self.triangle_ref.reflectivity.dot(ONE) / 3.0
        if random.real64() < reflectivity_mean:
            color = self.triangle_ref.reflectivity * (1.0 / reflectivity_mean)
            _2pr1 = pi * 2.0 * random.real64()
            sr2 = sqrt(random.real64())
            x = (cos(_2pr1) * sr2)
            y = (sin(_2pr1) * sr2)
            z = sqrt(1.0 - (sr2 * sr2))
            normal = self.triangle_ref.normal
            tangent = self.triangle_ref.tangent
            if normal.dot(in_direction) < 0.0:
                normal = -normal
            out_direction = (tangent * x) + (normal.cross(tangent) * y) + \
                (normal * z)
            return out_direction, color
        else:
            return ZERO, ZERO
