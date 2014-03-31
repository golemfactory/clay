import sys
sys.path.append( '../manager')

from threading import Thread, Lock
import time

from vm import PythonVM
from nodestatesnapshot import TaskChunkStateSnapshot

class TaskComputer:

    ######################
    def __init__( self, taskServer, estimatedPerformance, taskRequestFrequency ):
        self.estimatedPerformance   = estimatedPerformance
        self.taskServer             = taskServer
        self.waitingForTask         = 0
        self.currentComputations    = []
        self.lock                   = Lock()
        self.lastTaskRequest        = time.time()
        self.taskRequestFrequency   = taskRequestFrequency

    ######################
    def taskGiven( self, taskId, srcCode, extraData, shortDescr ):
        if self.waitingForTask:
            self.__computeTask( taskId, srcCode, extraData, shortDescr )
            self.waitingForTask = 0
            return True
        else:
            return False

    ######################
    def taskRequestRejected( self, taskId, reason ):
        print "Task {} request rejected: {}".format( taskId, reason )
        assert self.waitingForTask
        self.waitingForTask = 0

    ######################
    def taskComputed( self, taskThread ):
        with self.lock:
            self.currentComputations.remove( taskThread )

            taskId      = taskThread.taskId
            extraData   = taskThread.extraData

            if taskThread.result:
                print "Task {} computed".format( taskId )
                self.taskServer.sendResults( taskId, extraData, taskThread.result )

    ######################
    def run( self ):
        if not self.waitingForTask:
            if time.time() - self.lastTaskRequest > self.taskRequestFrequency:
                if len( self.currentComputations ) == 0:
                    self.lastTaskRequest = time.time()
                    self.__askForTask()

    ######################
    def getProgresses( self ):
        ret = {}
        for c in self.currentComputations:
            tcss = TaskChunkStateSnapshot( c.getTaskId(), 0.0, 0.0, c.getProgress(), c.getTaskShortDescr()  ) #FIXME: cpu power and estimated time left
            ret[ c.taskId ] = tcss

        return ret

    ######################
    def __askForTask( self ):
        self.waitingForTask = self.taskServer.requestTask( self.estimatedPerformance )

    ######################
    def __computeTask( self, taskId, srcCode, extraData, shortDescr ):
        tt = PyTaskThread( self, taskId, srcCode, extraData, shortDescr ) 
        self.currentComputations.append( tt )
        tt.start()


class TaskThread( Thread ):
    ######################
    def __init__( self, taskComputer, taskId, srcCode, extraData, shortDescr ):
        super( TaskThread, self ).__init__()

        self.taskComputer   = taskComputer
        self.vm             = None
        self.taskId         = taskId
        self.srcCode        = srcCode
        self.extraData      = extraData
        self.shortDescr     = shortDescr
        self.result         = None
        self.done           = False
        self.lock           = Lock()

    ######################
    def getTaskId( self ):
        return self.taskId

    ######################
    def getTaskShortDescr( self ):
        return self.shortDescr

    ######################
    def getProgress( self ):
        with self.lock:
            return self.vm.getProgress()

    ######################
    def run( self ):
        print "RUNNING "
        self.__doWork()
        self.taskComputer.taskComputed( self )
        self.done = True

    ######################
    def __doWork( self ):
        self.result = self.vm.runTask( self.srcCode, self.extraData )


class PyTaskThread( TaskThread ):
    ######################
    def __init__( self, taskComputer, taskId, srcCode, extraData, shortDescr ):
        super( PyTaskThread, self ).__init__( taskComputer, taskId, srcCode, extraData, shortDescr )
        self.vm = PythonVM()