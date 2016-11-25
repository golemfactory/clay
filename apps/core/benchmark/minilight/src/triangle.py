#  MiniLight Python : minimal global illumination renderer
#
#  Harrison Ainsworth / HXA7241 and Juraj Sukop : 2007-2008, 2013.
#  http://www.hxa.name/minilight


from math import sqrt
from vector3f import Vector3f, ZERO, ONE, MAX
from randommini import Random

import re
SEARCH = re.compile('(\(.+\))\s*(\(.+\))\s*(\(.+\))\s*(\(.+\))\s*(\(.+\))'
   ).search

TOLERANCE = 1.0 / 1024.0
EPSILON   = 1.0 / 1048576.0

class Triangle(object):

    def __init__(self, in_stream):
        for l in in_stream:
            if type(l) == type(u""):
                line = l.encode('ascii','ignore')
            else:
                line = l
            if not line.isspace():
                v0, v1, v2, r, e = SEARCH(line).groups()
                self.vertexs = map(Vector3f, [v0, v1, v2])
                self.edge0 = Vector3f(v1) - Vector3f(v0)
                self.edge3 = Vector3f(v2) - Vector3f(v0)
                self.reflectivity = Vector3f(r).clamped(ZERO, ONE)
                self.emitivity = Vector3f(e).clamped(ZERO, MAX)
                edge1 = Vector3f(v2) - Vector3f(v1)
                self.tangent = self.edge0.unitize()
                self.normal = self.tangent.cross(edge1).unitize()
                pa2 = self.edge0.cross(edge1)
                self.area = sqrt(pa2.dot(pa2)) * 0.5
                return
        raise StopIteration

    def get_bound(self):
        bound = list(self.vertexs[2]) + list(self.vertexs[2])
        for i in range(3):
            v = self.vertexs[i]
            for j in range(6):
                d, m = -1 if (j >= 3) else 1, j % 3
                a = v[m] - (d * TOLERANCE)
                if ((a - bound[j]) * d) < 0.0:
                    bound[j] = a
        return bound

    def get_intersection(self, ray_origin, ray_direction):
        e1x = self.edge0.x; e1y = self.edge0.y; e1z = self.edge0.z
        e2x = self.edge3.x; e2y = self.edge3.y; e2z = self.edge3.z
        pvx = ray_direction.y * e2z - ray_direction.z * e2y
        pvy = ray_direction.z * e2x - ray_direction.x * e2z
        pvz = ray_direction.x * e2y - ray_direction.y * e2x
        det = e1x * pvx + e1y * pvy + e1z * pvz
        if -EPSILON < det < EPSILON:
            return None
        inv_det = 1.0 / det
        v0 = self.vertexs[0]
        tvx = ray_origin.x - v0.x
        tvy = ray_origin.y - v0.y
        tvz = ray_origin.z - v0.z
        u = (tvx * pvx + tvy * pvy + tvz * pvz) * inv_det
        if u < 0.0 or u > 1.0:
            return None
        qvx = tvy * e1z - tvz * e1y
        qvy = tvz * e1x - tvx * e1z
        qvz = tvx * e1y - tvy * e1x
        v = (ray_direction.x * qvx + ray_direction.y * qvy + ray_direction.z *
            qvz) * inv_det
        if v < 0.0 or u + v > 1.0:
            return None
        t = (e2x * qvx + e2y * qvy + e2z * qvz) * inv_det
        if t < 0.0:
            return None
        return t

    def get_sample_point(self, random):
        sqr1 = sqrt(random.real64())
        r2 = random.real64()
        a = 1.0 - sqr1
        b = (1.0 - r2) * sqr1
        return self.edge0 * a + self.edge3 * b + self.vertexs[0]
