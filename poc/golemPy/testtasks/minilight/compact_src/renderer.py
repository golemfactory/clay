from math import sqrt, cos, pi, sin, tan
from io import StringIO
import re

################# RANDOM

SEED = 987654321

class Random(object):

    #def __init__(self):
    #    ul = uuid4().int
    #    ui = [ int( (ul >> (i * 32)) & 0xFFFFFFFFL ) for i in range(4) ]
    #    si = [ ui[i] if (ui[i] >= SEED_MINS[i]) else SEED for i in range(4) ]
    #    self.state0, self.state1, self.state2, self.state3 = si
    #    self.id = "%08X" % self.state3
    def __init__(self):
        self.state0 = self.state1 = self.state2 = self.state3 = SEED

    def int32u(self):
        self.state0 = (((self.state0 & 0xFFFFFFFE) << 18) & 0xFFFFFFFF) ^ \
                      ((((self.state0 <<  6) & 0xFFFFFFFF) ^ self.state0) >> 13)
        self.state1 = (((self.state1 & 0xFFFFFFF8) <<  2) & 0xFFFFFFFF) ^ \
                      ((((self.state1 <<  2) & 0xFFFFFFFF) ^ self.state1) >> 27)
        self.state2 = (((self.state2 & 0xFFFFFFF0) <<  7) & 0xFFFFFFFF) ^ \
                      ((((self.state2 << 13) & 0xFFFFFFFF) ^ self.state2) >> 21)
        self.state3 = (((self.state3 & 0xFFFFFF80) << 13) & 0xFFFFFFFF) ^ \
                      ((((self.state3 <<  3) & 0xFFFFFFFF) ^ self.state3) >> 12)
        return self.state0 ^ self.state1 ^ self.state2 ^ self.state3

    def real64(self):
        int0, int1 = self.int32u(), self.int32u()
        return (float((int0 < 2147483648) and int0 or (int0 - 4294967296)) *
            (1.0 / 4294967296.0)) + 0.5 + \
            (float(int1 & 0x001FFFFF) * (1.0 / 9007199254740992.0))

################# VECTOR

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
        return "({0.x}, {0.y}, {0.z})".format( self )

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

################# SPATIAL INDEX

MAX_LEVELS = 44
MAX_ITEMS  =  8

class SpatialIndex(object):

    def __init__(self, arg, items, level=0):
        if type(arg) == Vector3f:
            items = [(item.get_bound(), item) for item in items]
            bound = list(arg) * 2
            for item in items:
                for j in range(6):
                    if (bound[j] > item[0][j]) ^ (j > 2):
                        bound[j] = item[0][j]
            size = max(list(Vector3f(bound[3:6]) - Vector3f(bound[0:3])))
            self.bound = bound[0:3] + list(Vector3f(bound[3:6]
                ).clamped(Vector3f(bound[0:3]) + Vector3f(size), MAX))
        else:
            self.bound = arg
        self.is_branch = len(items) > MAX_ITEMS and level < MAX_LEVELS - 1
        if self.is_branch:
            q1 = 0
            self.vector = [None] * 8
            for s in range(8):
                sub_bound = []
                for j in range(6):
                    m = j % 3
                    if (((s >> m) & 1) != 0) ^ (j > 2):
                        sub_bound.append((self.bound[m] + self.bound[m + 3]) *
                            0.5)
                    else:
                        sub_bound.append(self.bound[j])
                sub_items = []
                for item in items:
                    item_bound = item[0]
                    if item_bound[3] >= sub_bound[0] and \
                       item_bound[0] < sub_bound[3] and \
                       item_bound[4] >= sub_bound[1] and \
                       item_bound[1] < sub_bound[4] and \
                       item_bound[5] >= sub_bound[2] and \
                       item_bound[2] < sub_bound[5]:
                           sub_items.append(item)
                q1 += 1 if len(sub_items) == len(items) else 0
                q2 = (sub_bound[3] - sub_bound[0]) < (TOLERANCE * 4.0)
                if len(sub_items) > 0:
                    self.vector[s] = SpatialIndex(sub_bound, sub_items,
                        MAX_LEVELS if q1 > 1 or q2 else level + 1)
        else:
            self.vector = [item[1] for item in items]

    def get_intersection(self, ray_origin, ray_direction, last_hit, start=None):
        start = start if start else ray_origin
        hit_object = hit_position = None
        if self.is_branch:
            sub_cell = 1 if start[0] >= (self.bound[0] + self.bound[3]) * 0.5 \
                else 0
            if start[1] >= (self.bound[1] + self.bound[4]) * 0.5:
                sub_cell |= 2
            if start[2] >= (self.bound[2] + self.bound[5]) * 0.5:
                sub_cell |= 4
            cell_position = start
            while True:
                if self.vector[sub_cell]:
                    hit_object, hit_position = self.vector[sub_cell
                        ].get_intersection(ray_origin, ray_direction, last_hit,
                        cell_position)
                    if hit_object:
                        break
                step = float(2**1024 - 2**971)
                axis = 0
                for i in range(3):
                    high = (sub_cell >> i) & 1
                    face = self.bound[i + high * 3] if (ray_direction[i] < 0.0
                        ) ^ (0 != high) else (self.bound[i] + self.bound[i + 3]
                        ) * 0.5
                    try:
                        distance = (face - ray_origin[i]) / ray_direction[i]
                    except:
                        distance = float(1e30000)
                    if distance <= step:
                        step = distance
                        axis = i
                if (((sub_cell >> axis) & 1) == 1) ^ (ray_direction[axis] <
                    0.0):
                    break
                cell_position = ray_origin + ray_direction * step
                sub_cell = sub_cell ^ (1 << axis)
        else:
            nearest_distance = float(2**1024 - 2**971)
            for item in self.vector:
                if item != last_hit:
                    distance = item.get_intersection(ray_origin, ray_direction)
                    if distance and (distance < nearest_distance):
                        hit = ray_origin + ray_direction * distance
                        if (self.bound[0] - hit[0] <= TOLERANCE) and \
                           (hit[0] - self.bound[3] <= TOLERANCE) and \
                           (self.bound[1] - hit[1] <= TOLERANCE) and \
                           (hit[1] - self.bound[4] <= TOLERANCE) and \
                           (self.bound[2] - hit[2] <= TOLERANCE) and \
                           (hit[2] - self.bound[5] <= TOLERANCE):
                               hit_object = item
                               hit_position = hit
                               nearest_distance = distance
        return hit_object, hit_position

################# SURFACE POINT

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


################# TRIANGLE

SEARCH_TRI = re.compile('(\(.+\))\s*(\(.+\))\s*(\(.+\))\s*(\(.+\))\s*(\(.+\))'
    ).search

TOLERANCE = 1.0 / 1024.0
EPSILON   = 1.0 / 1048576.0

class Triangle(object):

    def __init__(self, in_stream):
        for l in in_stream:
            if type( l ) == type( u"" ):
                line = l.encode('ascii','ignore')
            else:
                line = l
            if not line.isspace():
                v0, v1, v2, r, e = SEARCH_TRI(line).groups()
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

################# RAYRACER

class RayTracer(object):

    def __init__(self, scene):
        self.scene_ref = scene

    def get_radiance(self, ray_origin, ray_direction, random, last_hit=None):
        hit_ref, hit_position = self.scene_ref.get_intersection(ray_origin,
            ray_direction, last_hit)
        if hit_ref:
            surface_point = SurfacePoint(hit_ref, hit_position)
            local_emission = ZERO if last_hit else \
                surface_point.get_emission(ray_origin, -ray_direction, False)
            illumination = self.sample_emitters(ray_direction, surface_point,
                random)
            next_direction, color = surface_point.get_next_direction( random,
                -ray_direction)
            reflection = ZERO if next_direction.is_zero() else color * \
                self.get_radiance(surface_point.position, next_direction,
                    random, surface_point.triangle_ref)
            return reflection + illumination + local_emission
        else:
            return self.scene_ref.get_default_emission(-ray_direction)

    def sample_emitters(self, ray_direction, surface_point, random):
        emitter_position, emitter_ref = self.scene_ref.get_emitter(random)
        if emitter_ref:
            emit_direction = (emitter_position - surface_point.position
                ).unitize()
            hit_ref, p = self.scene_ref.get_intersection(
                surface_point.position, emit_direction,
                surface_point.triangle_ref)
            emission_in = SurfacePoint(emitter_ref, emitter_position
                ).get_emission(surface_point.position, -emit_direction, True) \
                if not hit_ref or emitter_ref == hit_ref else ZERO
            return surface_point.get_reflection(emit_direction,
                emission_in * self.scene_ref.emitters_count(), -ray_direction)
        else:
            return ZERO

################# CAMERA

SEARCH_CAM = re.compile('(\(.+\))\s*(\(.+\))\s*(\S+)').search

VIEW_ANGLE_MIN =  10.0
VIEW_ANGLE_MAX = 160.0

class Camera(object):

    def __init__(self, in_stream):
        for l in in_stream:
            if type( l ) == type( u"" ):
                line = l.encode('ascii','ignore')
            else:
                line = l
            if not line.isspace():
                p, d, a = SEARCH_CAM(line).groups()
                self.view_position = Vector3f(p)
                self.view_direction = Vector3f(d).unitize()
                if self.view_direction.is_zero():
                    self.view_direction = Vector3f(0.0, 0.0, 1.0)
                self.view_angle = min(max(VIEW_ANGLE_MIN, float(a)),
                    VIEW_ANGLE_MAX) * (pi / 180.0)
                self.right = Vector3f(0.0, 1.0, 0.0).cross(self.view_direction
                    ).unitize()
                if self.right.is_zero():
                    self.up = Vector3f(0.0, 0.0,
                        1.0 if self.view_direction.y else -1.0)
                    self.right = self.up.cross(self.view_direction).unitize()
                else:
                    self.up = self.view_direction.cross(self.right).unitize()
                break

    def __str__(self):
        return "{} {} {} {} {} ".format( self.view_position, self.view_angle, self.up, self.right, self.view_direction )

    def pixel_accumulated_radiance(self, scene, random, width, height, x, y, aspect, num_samples):
        raytracer = RayTracer(scene)
        acc_radiance = [ 0.0, 0.0, 0.0 ]

        for i in range(num_samples):
            x_coefficient = ((x + random.real64()) * 2.0 / width) - 1.0
            y_coefficient = ((y + random.real64()) * 2.0 / height) - 1.0

            offset = self.right * x_coefficient + self.up * (y_coefficient * aspect)

            sample_direction = (self.view_direction + (offset * tan(self.view_angle * 0.5))).unitize()

            radiance = raytracer.get_radiance(self.view_position,sample_direction, random)

            acc_radiance[ 0 ] += radiance[ 0 ]          
            acc_radiance[ 1 ] += radiance[ 1 ]          
            acc_radiance[ 2 ] += radiance[ 2 ]          				
        
        return Vector3f( acc_radiance[ 0 ], acc_radiance[ 1 ], acc_radiance[ 2 ] )

    def get_frame(self, scene, random, image):
        raytracer = RayTracer(scene)
        aspect = float(image.height) / float(image.width)
        for y in range(image.height):
            for x in range(image.width):
                x_coefficient = ((x + random.real64()) * 2.0 / image.width) \
                    - 1.0
                y_coefficient = ((y + random.real64()) * 2.0 / image.height) \
                    - 1.0
                offset = self.right * x_coefficient + \
                    self.up * (y_coefficient * aspect)
                sample_direction = (self.view_direction +
                    (offset * tan(self.view_angle * 0.5))).unitize()
                radiance = raytracer.get_radiance(self.view_position,
                    sample_direction, random)
                image.add_to_pixel(x, y, radiance)

################# SCENE

SEARCH_SCN = re.compile('(\(.+\))\s*(\(.+\))').search

MAX_TRIANGLES = 0x1000000

class Scene(object):

    def __init__(self, in_stream, eye_position):
        for l in in_stream:
            if type( l ) == type( u"" ):
                line = l.encode('ascii','ignore')
            else:
                line = l
            if not line.isspace():
                s, g = SEARCH_SCN(line).groups()
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

################# RENDER TASK DESCRIPTORS

class RenderTaskDesc:

    @classmethod
    def createRenderTaskDesc( cls, id, x, y, w, h, num_pixels, num_samples ):
        return RenderTaskDesc( id, x, y, w, h, num_pixels, num_samples )

    def __init__( self, id, x, y, w, h, num_pixels, num_samples ):
        self.id = id
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.num_pixels = num_pixels
        self.num_samples = num_samples

    def isValid( self ):
        if self.x < 0 or self.y < 0 or self.x >= self.w or self.y >= self.h:
            print "Invalid dimensions loc( {}, {} ), size( {}, {} )".format( self.x, self.y, self.w, self.h )
            return False
        
        if self.num_samples < 1 or self.num_pixels < 1:
            print "Not enough pixels {} or samples {} specified".format( self.num_pixels, self.num_samples )
            return False

        totalPixels = self.w * self.h
        leftOver = totalPixels - self.h * self.y + self.x

        if leftOver < self.num_pixels:
            print "Too many pixels ({}) specified, for current descriptor at most {} pixels can be rendered".format( self.num_pixels, leftOver )
            return False

        return True

    def getID( self ):
        return self.id

    def getX( self ):
        return self.x

    def getY( self ):
        return self.y

    def getW( self ):
        return self.w

    def getH( self ):
        return self.h

    def getNumPixels( self ):
        return self.num_pixels

    def getNumSamples( self ):
        return self.num_samples

class RenderTask:
    
    @classmethod
    def createRenderTask( cls, renderTaskDesc, scene_data, callback ):

        if not renderTaskDesc.isValid():
            return None

        try:
            data_stream = StringIO( scene_data )
            camera  = Camera( data_stream )
            scene   = Scene( data_stream, camera.view_position )
        except Exception as ex:
            print "Failed to read camera or scene from serialized data"
            print ex
            #if verbose -> dump all data
            return None

        return RenderTask( renderTaskDesc, camera, scene, callback )

    def __init__( self, desc, camera, scene, callback ):
        self.desc = desc
        self.camera = camera
        self.scene = scene
        self.callback = callback

    def isValid( self ):
        return self.desc.isValid()
    
    def getDesc( self ):
        return self.desc

    def getCamera( self ):
        return self.camera

    def getScene( self ):
        return self.scene

class RenderTaskResult:

    @classmethod
    def createRenderTaskResult( cls, renderTaskDesc, pixelData ):
        if not renderTaskDesc.isValid():
            return None

        lenPixels = len( pixelData )
        if lenPixels % 3 != 0:
            print "Pixel data len not divisible by 3".format( lenPixels )
            return None

        if lenPixels // 3 != renderTaskDesc.getNumPixels():
            print "Pixel data length {} differs from descriptor data length {}".format( lenPixels, renderTaskDesc.getNumPixels() )
            return None

        return RenderTaskResult( renderTaskDesc, pixelData )

    def __init__( self, desc, pixelData ):
        self.desc = desc
        self.pixelData = pixelData

    def getDesc( self ):
        return self.desc

    def getPixelData( self ):
        return self.pixelData

################# RENDER WORKER

class RenderWorker:

    @classmethod
    def createWorker( cls, renderTask ):
        
        if not renderTask.isValid():
            return None

        return RenderWorker( renderTask )

    def __init__( self, task ):
        assert isinstance( task, RenderTask )

        self.task = task

        self.random     = Random()
        self.raytracer  = RayTracer( task.getScene() )
        self.progress   = 0.0

    def getProgress( self ):
        return self.progress

    def sample_radiance( self, x, y, w, h, aspect, camera, scene, num_samples ):
        acc_radiance = [ 0.0, 0.0, 0.0 ]

        for i in range(num_samples):
            x_coefficient = ((x + self.random.real64()) * 2.0 / w) - 1.0
            y_coefficient = ((y + self.random.real64()) * 2.0 / h) - 1.0

            offset = camera.right * x_coefficient + camera.up * (y_coefficient * aspect)

            sample_direction = (camera.view_direction + (offset * tan(camera.view_angle * 0.5))).unitize()

            radiance = self.raytracer.get_radiance(camera.view_position,sample_direction, self.random)

            acc_radiance[ 0 ] += radiance[ 0 ]          
            acc_radiance[ 1 ] += radiance[ 1 ]          
            acc_radiance[ 2 ] += radiance[ 2 ]          				
        
        return Vector3f( acc_radiance[ 0 ], acc_radiance[ 1 ], acc_radiance[ 2 ] )

    def getXY( self, idx, w ):
        return idx % w, idx // w

    def renderingFinished( self, pixels ):
        result = RenderTaskResult.createRenderTaskResult( self.task.getDesc(), pixels )

        if result:
            if self.task.callback:
                self.task.callback( result )
        else:
            print "Failed to acquire result"
            
        return result

    def render( self ):
        desc = self.task.getDesc()
        
        x, y, w, h              =  desc.getX(), desc.getY(), desc.getW(), desc.getH()
        num_pixels, num_samples = desc.getNumPixels(), desc.getNumSamples()
        aspect  = float( h ) / float( w )
        offset  = y * w + x
        id = desc.getID()

        pixels  = [0.0] * 3 * num_pixels

        cam = self.task.getCamera()
        scn = self.task.getScene()

        for k in range( num_pixels ):
            x, y = self.getXY( k + offset, w )

            radiance = self.sample_radiance( x, y, w, h, aspect, cam, scn, num_samples )

            pixels[ 3 * k + 0 ] = radiance[ 0 ]                
            pixels[ 3 * k + 1 ] = radiance[ 1 ]                
            pixels[ 3 * k + 2 ] = radiance[ 2 ]                

            progress = float( k + 1 ) / float( num_pixels )

        return self.renderingFinished( pixels )

def compute( output ):

    #FIXME: input data (extra data) - external
    #FIXME: scene data (scene) - external

    #FIXME: read from extra data

    #FIXME: read scene from the node
    task_data = u'''
(0.278 0.275 -0.789) (0 0 1) 40


(0.0906 0.0943 0.1151) (0.1 0.09 0.07)


(0.556 0.000 0.000) (0.006 0.000 0.559) (0.556 0.000 0.559)  (0.7 0.7 0.7) (0 0 0)
(0.006 0.000 0.559) (0.556 0.000 0.000) (0.003 0.000 0.000)  (0.7 0.7 0.7) (0 0 0)

(0.556 0.000 0.559) (0.000 0.549 0.559) (0.556 0.549 0.559)  (0.7 0.7 0.7) (0 0 0)
(0.000 0.549 0.559) (0.556 0.000 0.559) (0.006 0.000 0.559)  (0.7 0.7 0.7) (0 0 0)

(0.006 0.000 0.559) (0.000 0.549 0.000) (0.000 0.549 0.559)  (0.7 0.2 0.2) (0 0 0)
(0.000 0.549 0.000) (0.006 0.000 0.559) (0.003 0.000 0.000)  (0.7 0.2 0.2) (0 0 0)

(0.556 0.000 0.000) (0.556 0.549 0.559) (0.556 0.549 0.000)  (0.2 0.7 0.2) (0 0 0)
(0.556 0.549 0.559) (0.556 0.000 0.000) (0.556 0.000 0.559)  (0.2 0.7 0.2) (0 0 0)

(0.556 0.549 0.559) (0.000 0.549 0.000) (0.556 0.549 0.000)  (0.7 0.7 0.7) (0 0 0)
(0.000 0.549 0.000) (0.556 0.549 0.559) (0.000 0.549 0.559)  (0.7 0.7 0.7) (0 0 0)

(0.343 0.545 0.332) (0.213 0.545 0.227) (0.343 0.545 0.227)  (0.7 0.7 0.7) (1000 1000 1000)
(0.213 0.545 0.227) (0.343 0.545 0.332) (0.213 0.545 0.332)  (0.7 0.7 0.7) (1000 1000 1000)


(0.474 0.165 0.225) (0.426 0.165 0.065) (0.316 0.165 0.272)  (0.7 0.7 0.7) (0 0 0)
(0.266 0.165 0.114) (0.316 0.165 0.272) (0.426 0.165 0.065)  (0.7 0.7 0.7) (0 0 0)

(0.266 0.000 0.114) (0.266 0.165 0.114) (0.316 0.165 0.272)  (0.7 0.7 0.7) (0 0 0)
(0.316 0.000 0.272) (0.266 0.000 0.114) (0.316 0.165 0.272)  (0.7 0.7 0.7) (0 0 0)

(0.316 0.000 0.272) (0.316 0.165 0.272) (0.474 0.165 0.225)  (0.7 0.7 0.7) (0 0 0)
(0.474 0.165 0.225) (0.316 0.000 0.272) (0.474 0.000 0.225)  (0.7 0.7 0.7) (0 0 0)

(0.474 0.000 0.225) (0.474 0.165 0.225) (0.426 0.165 0.065)  (0.7 0.7 0.7) (0 0 0)
(0.426 0.165 0.065) (0.426 0.000 0.065) (0.474 0.000 0.225)  (0.7 0.7 0.7) (0 0 0)

(0.426 0.000 0.065) (0.426 0.165 0.065) (0.266 0.165 0.114)  (0.7 0.7 0.7) (0 0 0)
(0.266 0.165 0.114) (0.266 0.000 0.114) (0.426 0.000 0.065)  (0.7 0.7 0.7) (0 0 0)


(0.133 0.330 0.247) (0.291 0.330 0.296) (0.242 0.330 0.456)  (0.7 0.7 0.7) (0 0 0)
(0.242 0.330 0.456) (0.084 0.330 0.406) (0.133 0.330 0.247)  (0.7 0.7 0.7) (0 0 0)

(0.133 0.000 0.247) (0.133 0.330 0.247) (0.084 0.330 0.406)  (0.7 0.7 0.7) (0 0 0)
(0.084 0.330 0.406) (0.084 0.000 0.406) (0.133 0.000 0.247)  (0.7 0.7 0.7) (0 0 0)

(0.084 0.000 0.406) (0.084 0.330 0.406) (0.242 0.330 0.456)  (0.7 0.7 0.7) (0 0 0)
(0.242 0.330 0.456) (0.242 0.000 0.456) (0.084 0.000 0.406)  (0.7 0.7 0.7) (0 0 0)

(0.242 0.000 0.456) (0.242 0.330 0.456) (0.291 0.330 0.296)  (0.7 0.7 0.7) (0 0 0)
(0.291 0.330 0.296) (0.291 0.000 0.296) (0.242 0.000 0.456)  (0.7 0.7 0.7) (0 0 0)

(0.291 0.000 0.296) (0.291 0.330 0.296) (0.133 0.330 0.247)  (0.7 0.7 0.7) (0 0 0)
(0.133 0.330 0.247) (0.133 0.000 0.247) (0.291 0.000 0.296)  (0.7 0.7 0.7) (0 0 0)'''

    #GET TASK
    extra_desc = RenderTaskDesc.createRenderTaskDesc( id, x, y, w, h, num_pixels, num_samples )
    task = RenderTask.createRenderTask( extra_desc, task_data, None )
    worker = RenderWorker.createWorker( task )

    #CALCULATE
    result = worker.render()
    
    #RETURN RESULT and write to proper stream
    data = result.getPixelData()
    #print len( data ) // 3
    #print data
    #print len( data ) // 3
    for p in data:
        output.append( p )

output = []

compute( output )