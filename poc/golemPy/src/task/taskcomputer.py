from threading import Thread, Lock
import time

class TaskComputer:
    ######################
    def __init__( self, taskServer, estimatedPerformance, taskRequestFrequency ):
        self.estimatedPerformance  = estimatedPerformance
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
    def taskGiven( self, task, extraData ):
        if self.waitingForTask:
            self.__computeTask( task, extraData )
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

            task        = taskThread.task
            extraData   = taskThread.extraData

            if task.taskResult:
                print "Task {} computed".format( task.taskHeader.id )
                self.taskServer.sendResults( task.taskHeader.id, extraData, task.taskResult )

    ######################
    def run( self ):
        if not self.waitingForTask:
            if time.time() - self.lastTaskRequest > self.taskRequestFrequency:
                self.askForTask()

    ######################
    def __computeTask( self, task, extraData ):
        tt = PyTaskThread( self, task, extraData ) 
        self.currentComputations.append( tt )
        tt.start()


class TaskThread( Thread ):
    ######################
    def __init__( self, taskComputer, task, extraData ):
        super( TaskThread, self ).__init__()
        self.taskManager = taskComputer
        self.vm = None
        self.task = task
        self.extraData = extraData
        self.done = False

    ######################
    def run( self ):
        print "RUNNING "
        self.doWork()
        self.taskComputer.taskComputed( self )
        self.done = True

    ######################
    def doWork( self ):
        self.vm.runTask( self.task, self.extraData )


class PyTaskThread( TaskThread ):
    ######################
    def __init__( self, taskComputer, task, extraData ):
        super( PyTaskThread, self ).__init__( taskComputer, task, extraData )
        self.vm = PythonVM()