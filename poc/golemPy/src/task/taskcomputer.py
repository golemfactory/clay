from threading import Thread, Lock
import time

from vm import PythonVM

class TaskComputer:
    ######################
    def __init__( self, taskServer, estimatedPerformance, taskRequestFrequency ):
        self.estimatedPerformance   = estimatedPerformance
        self.taskServer             = taskServer
        self.waitingForTask         = False
        self.currentComputations    = []
        self.lock                   = Lock()
        self.lastTaskRequest        = time.time()
        self.taskRequestFrequency   = taskRequestFrequency

    ######################
    def askForTask( self ):
        self.waitingForTask = self.taskServer.requestTask( self.estimatedPerformance )

    ######################
    def taskGiven( self, taskId, srcCode, extraData ):
        if self.waitingForTask:
            self.__computeTask( taskId, srcCode, extraData )
            self.waitingForTask = False
            return True
        else:
            return False

    def taskRequestRejected( self, taskId, reason ):
        print "Task {} request rejected: {}".format( taskId, reason )
        assert self.waitingForTask
        self.waitingForTask = False

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
                self.lastTaskRequest = time.time()
                self.askForTask()

    ######################
    def __computeTask( self, taskId, srcCode, extraData ):
        tt = PyTaskThread( self, taskId, srcCode, extraData ) 
        self.currentComputations.append( tt )
        tt.start()


class TaskThread( Thread ):
    ######################
    def __init__( self, taskComputer, taskId, srcCode, extraData ):
        super( TaskThread, self ).__init__()

        self.taskComputer   = taskComputer
        self.vm             = None
        self.taskId         = taskId
        self.srcCode        = srcCode
        self.extraData      = extraData
        self.result         = None
        self.done           = False

    ######################
    def run( self ):
        print "RUNNING "
        self.doWork()
        self.taskComputer.taskComputed( self )
        self.done = True

    ######################
    def doWork( self ):
        self.result = self.vm.runTask( self.srcCode, self.extraData )


class PyTaskThread( TaskThread ):
    ######################
    def __init__( self, taskComputer, taskId, srcCode, extraData ):
        super( PyTaskThread, self ).__init__( taskComputer, taskId, srcCode, extraData )
        self.vm = PythonVM()