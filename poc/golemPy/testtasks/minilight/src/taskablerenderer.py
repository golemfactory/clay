from rendertask import RenderTask, RenderTaskDesc, RenderTaskResult
from threading import Lock
from time import time

class TaskableRenderer:

    def __init__( self, w, h, num_samples, scene_data, preferredTaskTimeSlice, timeoutTime ):
        self.w = w
        self.h = h
        self.num_samples = num_samples
        self.scene_data = scene_data

        self.timeoutTime = timeoutTime
        self.preferredTaskTime = preferredTaskTimeSlice 
        self.startTime = time()

        #FIXME: validate scene data here
        #FIXME: this should be a bit more sophisticated structure (to collect more than one result per pixel and to calc some stats using this data)
        self.data = [0.0] * w * h * 3
        self.pixelsCalculated = 0

        self.nextPixel = 0
        self.pixelsLeft = w * h
        self.totalTasks = 0
        self.activeTasks = 0

        self.lock = Lock()

    def printStats( self ):
        print "Total accepted tasks:     {}".format( self.totalTasks )
        print "Active tasks:             {}".format( self.activeTasks )
        print "Total pixels calculated : {}".format( self.pixelsCalculated )
        print "Active pixels (in tasks): {}".format( self.nextPixel - self.pixelsCalculated )
        print "Unallocated pixels:       {}".format( self.pixelsLeft )
        print "Progress:                 {}".format( self.getProgress() )

    def start( self ):
        self.startTime = time()

    def isFinished( self ):
        return self.pixelsCalculated == self.w * self.h

    def getProgress( self ):
        return float( self.pixelsCalculated ) / float( self.w * self.h )

    def getResult( self ):
        if isFinished():
            return None
        return None

    def __createTask( self, curPixel, numPixels ):
        x = curPixel % self.w
        y = curPixel // self.w

        desc = RenderTaskDesc.createRenderTaskDesc( self.totalTasks, x, y, self.w, self.h, numPixels, self.num_samples )
        task = RenderTask.createRenderTask( desc, self.scene_data, self.taskFinished )

        return task

    #estimated speed means rays per second
    def getNextTask( self, estimatedSpeed ):
        with self.lock:
            timeLeft = self.timeoutTime - ( time() - self.startTime )
        
            timeSlice = self.preferredTaskTime
            if timeLeft < self.preferredTaskTime:
                timeSlice = timeLeft

            if timeSlice <= 0.001:
                print "Overtime - we're doomed, but we still want the calculation to progress"
                timeSlice = self.preferredTaskTime

            numPixels = int( estimatedSpeed / self.num_samples * timeSlice )
            
            if numPixels < 1:
                numPixels = 1

            if numPixels > self.pixelsLeft:
                numPixels = self.pixelsLeft

            if numPixels == 0:
                print "All pixels have beend already dispatched"
                return None

            task = self.__createTask( self.nextPixel, numPixels )

            self.nextPixel += numPixels
            self.pixelsLeft -= numPixels
            self.activeTasks += 1
            self.totalTasks += 1

            print "Task {:5} with {} pixels at ({}, {}) - ASSIGNED".format( task.desc.getID(), task.desc.getNumPixels(), task.desc.getX(), task.desc.getY() )

            return task

    def taskFinished( self, result ):
        assert isinstance( result, RenderTaskResult )
        assert result.desc.getW() == self.w and result.desc.getH() == self.h

        print "Task {:5} with {} pixels at ({}, {}) - FINISHED".format( result.desc.getID(), result.desc.getNumPixels(), result.desc.getX(), result.desc.getY() )

        desc    = result.getDesc()
        pixels  = result.getPixelData()
        offset  = 3 * desc.getY() * desc.getW() + desc.getX()

        with self.lock:
            self.activeTasks -= 1
            self.pixelsCalculated += result.getDesc().getNumPixels()

        for k in range( 3 * desc.getNumPixels() ):
            self.data[ k + offset ] = pixels[ k ]
