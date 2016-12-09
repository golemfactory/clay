from math import tan

from rendertask import RenderTaskDesc, RenderTask, RenderTaskResult
from randommini import Random
from vector3f import Vector3f
from raytracer import RayTracer

class RenderWorker:

    @classmethod
    def createWorker(cls, renderTask ):
        
        if not renderTask.isValid():
            return None

        return RenderWorker(renderTask)

    def __init__(self, task):
        assert isinstance(task, RenderTask)

        self.task = task

        self.random     = Random()
        self.raytracer  = RayTracer(task.getScene())
        self.progress   = 0.0

    def get_progress(self):
        return self.progress

    def sample_radiance(self, x, y, w, h, aspect, camera, scene, num_samples):
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
        
        return Vector3f(acc_radiance[ 0 ], acc_radiance[ 1 ], acc_radiance[ 2 ])

    def getXY(self, idx, w):
        return idx % w, idx // w

    def renderingFinished(self, pixels):
        result = RenderTaskResult.createRenderTaskResult(self.task.getDesc(), pixels)

        if result:
            if self.task.callback:
                self.task.callback(result)
        else:
            print "Failed to acquire result"
            
        return result

    def render(self):
        desc = self.task.getDesc()
        
        x, y, w, h              =  desc.getX(), desc.getY(), desc.getW(), desc.getH()
        num_pixels, num_samples = desc.getNumPixels(), desc.getNumSamples()
        aspect  = float(h) / float(w)
        offset  = y * w + x
        id = desc.getID()

        pixels  = [0.0] * 3 * num_pixels

        cam = self.task.getCamera()
        scn = self.task.getScene()

        for k in range(num_pixels):
            x, y = self.getXY(k + offset, w)

            radiance = self.sample_radiance(x, y, w, h, aspect, cam, scn, num_samples)

            pixels[ 3 * k + 0 ] = radiance[ 0 ]                
            pixels[ 3 * k + 1 ] = radiance[ 1 ]                
            pixels[ 3 * k + 2 ] = radiance[ 2 ]                

            progress = float(k + 1) / float(num_pixels)

        return self.renderingFinished(pixels)
