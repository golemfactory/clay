from io import StringIO
from camera import Camera
from scene import Scene

class RenderTaskDesc:

    @classmethod
    def createRenderTaskDesc(cls, id, x, y, w, h, num_pixels, num_samples):
        return RenderTaskDesc(id, x, y, w, h, num_pixels, num_samples)

    def __init__(self, id, x, y, w, h, num_pixels, num_samples):
        self.id = id
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.num_pixels = num_pixels
        self.num_samples = num_samples

    def isValid(self):
        if self.x < 0 or self.y < 0 or self.x >= self.w or self.y >= self.h:
            print "Invalid dimensions loc({}, {}), size({}, {})".format(self.x, self.y, self.w, self.h)
            return False
        
        if self.num_samples < 1 or self.num_pixels < 1:
            print "Not enough pixels {} or samples {} specified".format(self.num_pixels, self.num_samples)
            return False

        totalPixels = self.w * self.h
        leftOver = totalPixels - self.w * self.y + self.x

        if leftOver < self.num_pixels:
            print "Too many pixels ({}) specified, for current descriptor at most {} pixels can be rendered".format(self.num_pixels, leftOver)
            return False

        return True

    def getID(self):
        return self.id

    def getX(self):
        return self.x

    def getY(self):
        return self.y

    def getW(self):
        return self.w

    def getH(self):
        return self.h

    def getNumPixels(self):
        return self.num_pixels

    def getNumSamples(self):
        return self.num_samples

class RenderTask:
    
    @classmethod
    def createRenderTask(cls, renderTaskDesc, scene_data, callback):

        if not renderTaskDesc.isValid():
            return None

        try:
            data_stream = StringIO(scene_data)
            camera  = Camera(data_stream)
            scene   = Scene(data_stream, camera.view_position)
        except Exception as ex:
            print "Failed to read camera or scene from serialized data"
            print ex
            #if verbose -> dump all data
            return None

        return RenderTask(renderTaskDesc, camera, scene, callback)

    def __init__(self, desc, camera, scene, callback):
        self.desc = desc
        self.camera = camera
        self.scene = scene
        self.callback = callback

    def isValid(self):
        return self.desc.isValid()
    
    def getDesc(self):
        return self.desc

    def getCamera(self):
        return self.camera

    def getScene(self):
        return self.scene

class RenderTaskResult:

    @classmethod
    def createRenderTaskResult(cls, renderTaskDesc, pixelData):
        if not renderTaskDesc.isValid():
            return None

        lenPixels = len(pixelData)
        if lenPixels % 3 != 0:
            print "Pixel data len not divisible by 3".format(lenPixels)
            return None

        if lenPixels // 3 != renderTaskDesc.getNumPixels():
            print "Pixel data length {} differs from descriptor data length {}".format(lenPixels, renderTaskDesc.getNumPixels())
            return None

        return RenderTaskResult(renderTaskDesc, pixelData)

    def __init__(self, desc, pixelData):
        self.desc = desc
        self.pixelData = pixelData

    def getDesc(self):
        return self.desc

    def get_pixel_data(self):
        return self.pixelData
