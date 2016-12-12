#  MiniLight Python : minimal global illumination renderer
#
#  Harrison Ainsworth / HXA7241 and Juraj Sukop : 2007-2008, 2013.
#  http://www.hxa.name/minilight


from triangle import Triangle, TOLERANCE
from vector3f import Vector3f, MAX

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
