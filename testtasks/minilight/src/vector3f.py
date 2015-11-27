#  MiniLight Python : minimal global illumination renderer
#
#  Harrison Ainsworth / HXA7241 and Juraj Sukop : 2007-2008, 2013.
#  http://www.hxa.name/minilight


from math import sqrt

class Vector3f(object):

    def __init__(self, *args):
        if len(args) == 1 and type(args[0]) == type(''):
            self.x, self.y, self.z = map(float, args[0].lstrip(' (').rstrip(') '
               ).split())
        elif type(args[0]) == Vector3f:
            self.x, self.y, self.z = args[0].x, args[0].y, args[0].z
        else:
            if type(args[0]) == list or type(args[0]) == tuple:
                args = args[0]
            self.x = self.y = self.z = float(args[0])
            if len(args) > 2:
                self.y, self.z = float(args[1]), float(args[2])

    def __str__(self):
        return "({0.x}, {0.y}, {0.z})".format(self)

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z

    def __getitem__(self, key):
        if key == 2:
            return self.z
        elif key == 1:
            return self.y
        else:
            return self.x

    def __neg__(self):
        return Vector3f(-self.x, -self.y, -self.z)

    def __add__(self, other):
        return Vector3f(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        return Vector3f(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, other):
        if type(other) == Vector3f:
            return Vector3f(self.x * other.x, self.y * other.y,
                self.z * other.z)
        else:
            return Vector3f(self.x * other, self.y * other, self.z * other)

    def is_zero(self):
        return self.x == 0.0 and self.y == 0.0 and self.z == 0.0

    def dot(self, other):
        return (self.x * other.x) + (self.y * other.y) + (self.z * other.z)

    def unitize(self):
        length = sqrt(self.x * self.x + self.y * self.y + self.z * self.z)
        one_over_length = 1.0 / length if length != 0.0 else 0.0
        return Vector3f(self.x * one_over_length, self.y * one_over_length,
            self.z * one_over_length)

    def cross(self, other):
        return Vector3f((self.y * other.z) - (self.z * other.y),
                        (self.z * other.x) - (self.x * other.z),
                        (self.x * other.y) - (self.y * other.x))

    def clamped(self, lo, hi):
        return Vector3f(min(max(self.x, lo.x), hi.x),
                        min(max(self.y, lo.y), hi.y),
                        min(max(self.z, lo.z), hi.z))

ZERO = Vector3f(0.0)
ONE = Vector3f(1.0)
MAX = Vector3f(float(2**1024 - 2**971))
