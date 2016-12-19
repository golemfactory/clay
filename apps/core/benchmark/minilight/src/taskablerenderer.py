from rendertask import RenderTask, RenderTaskDesc, RenderTaskResult
from threading import Lock
from time import time

class TaskableRenderer:

    def __init__(self, w, h, num_samples, scene_data, preferredTaskTimeSlice, timeoutTime):
        self.w = w
        self.h = h
        self.num_samples = num_samples
        self.scene_data = scene_data

        self.timeoutTime = timeoutTime
        self.preferredTaskTime = preferredTaskTimeSlice 
        self.start_time = time()

        # TODO: validate scene data here
        # TODO: collect more than one result per pixel
        # TODO: calc some stats using this data
        self.data = [0.0] * w * h * 3
        self.pixelsCalculated = 0

        self.nextPixel = 0
        self.pixelsLeft = w * h
        self.total_tasks = 0
        self.active_tasks = 0

        self.lock = Lock()

    def printStats(self):
        print "  Total accepted tasks:     {}".format(self.total_tasks)
        print "  Active tasks:             {}".format(self.active_tasks)
        print "  Total pixels calculated : {}".format(self.pixelsCalculated)
        print "  Active pixels (in tasks): {}".format(self.nextPixel - self.pixelsCalculated)
        print "  Unallocated pixels:       {}".format(self.pixelsLeft)
        print "  Progress:                 {}".format(self.get_progress())

    def start(self):
        self.start_time = time()

    def isFinished(self):
        return self.pixelsCalculated == self.w * self.h

    def hasMoreTasks(self):
        return self.pixelsLeft > 0

    def get_progress(self):
        return float(self.pixelsCalculated) / float(self.w * self.h)

    def getResult(self):
        if self.isFinished():
            return self.data

        return None

    def __createTaskDesc(self, curPixel, num_pixels):
        x = curPixel % self.w
        y = curPixel // self.w

        desc = RenderTaskDesc.createRenderTaskDesc(self.total_tasks, x, y, self.w, self.h, num_pixels, self.num_samples)

        return desc

    def __createTask(self, curPixel, num_pixels):
        desc = self.__createTaskDesc(self, curPixel, num_pixels)
        task = RenderTask.createRenderTask(desc, self.scene_data, self.task_finished)

        return task

    #estimated speed means rays per second
    def getNextTaskDesc(self, estimatedSpeed):
        with self.lock:
            timeLeft = self.timeoutTime - (time() - self.start_time)
        
            timeSlice = self.preferredTaskTime
            if timeLeft < self.preferredTaskTime:
                timeSlice = timeLeft

            if timeSlice <= 0.001:
                print "Overtime - we're doomed, but we still want the calculation to progress"
                timeSlice = self.preferredTaskTime

            num_pixels = int(estimatedSpeed / self.num_samples * timeSlice)
            
            if num_pixels < 1:
                num_pixels = 1

            if num_pixels > self.pixelsLeft:
                num_pixels = self.pixelsLeft

            if num_pixels == 0:
                print "All pixels have beend already dispatched"
                return None

            task_desc = self.__createTaskDesc(self.nextPixel, num_pixels)

            self.nextPixel += num_pixels
            self.pixelsLeft -= num_pixels
            self.active_tasks += 1
            self.total_tasks += 1

            print "ASSIGNED Task {:5} with {:5} pixels at ({}, {}) at {} rays/s".format(task_desc.getID(), task_desc.getNumPixels(), task_desc.getX(), task_desc.getY(), estimatedSpeed)

            return task_desc


    #estimated speed means rays per second
    def getNextTask(self, estimatedSpeed):
        with self.lock:
            timeLeft = self.timeoutTime - (time() - self.start_time)
        
            timeSlice = self.preferredTaskTime
            if timeLeft < self.preferredTaskTime:
                timeSlice = timeLeft

            if timeSlice <= 0.001:
                print "Overtime - we're doomed, but we still want the calculation to progress"
                timeSlice = self.preferredTaskTime

            num_pixels = int(estimatedSpeed / self.num_samples * timeSlice)
            
            if num_pixels < 1:
                num_pixels = 1

            if num_pixels > self.pixelsLeft:
                num_pixels = self.pixelsLeft

            if num_pixels == 0:
                print "All pixels have beend already dispatched"
                return None

            task = self.__createTask(self.nextPixel, num_pixels)

            self.nextPixel += num_pixels
            self.pixelsLeft -= num_pixels
            self.active_tasks += 1
            self.total_tasks += 1

            print "ASSIGNED Task {:5} with {:5} pixels at ({}, {}) at {} rays/s".format(task.desc.getID(), task.desc.getNumPixels(), task.desc.getX(), task.desc.getY(), estimatedSpeed)

            return task

    def task_finished(self, result):
        assert isinstance(result, RenderTaskResult)
        assert result.desc.getW() == self.w and result.desc.getH() == self.h

        desc    = result.getDesc()
        pixels  = result.get_pixel_data()
        x, y, w = desc.getX(), desc.getY(), desc.getW()
        offset  = 3 * (w * y + x)

        with self.lock:
            self.active_tasks -= 1
            self.pixelsCalculated += result.getDesc().getNumPixels()

        print "FINISHED Task {:5} with {:5} pixels at ({}, {}) with progress: {} %".format(result.desc.getID(), result.desc.getNumPixels(), result.desc.getX(), result.desc.getY(), 100.0 * self.get_progress())

        for k in range(3 * desc.getNumPixels()):
            self.data[ k + offset ] = pixels[ k ]
