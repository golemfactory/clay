
import sys
sys.path.append( '../manager')

from threading import Thread, Lock
import time
import os

from vm import PythonVM
from NodeStateSnapshot import TaskChunkStateSnapshot
from ResourcesManager import ResourcesManager
from Environment import TaskComputerEnvironment

class TaskComputer:

    ######################
    def __init__( self, clientUid, taskServer, estimatedPerformance, taskRequestFrequency ):
        self.clientUid              = clientUid
        self.estimatedPerformance   = estimatedPerformance
        self.taskServer             = taskServer
        self.waitingForTask         = 0
        self.currentComputations    = []
        self.lock                   = Lock()
        self.lastTaskRequest        = time.time()
        self.taskRequestFrequency   = taskRequestFrequency

        self.env                    = TaskComputerEnvironment( "ComputerRes", self.clientUid )

        self.resourceManager        = ResourcesManager( self.env, self )

        self.curSrcCode             = ""
        self.curExtraData           = None
        self.curShortDescr          = None

    ######################
    def taskGiven( self, taskId, srcCode, extraData, shortDescr ):
        if self.waitingForTask:
            self.__requestResource( taskId, self.resourceManager.getResourceHeader( taskId ) )
            self.curSrcCode             = srcCode
            self.curExtraData           = extraData
            self.curShortDescr          = shortDescr
            return True
        else:
            return False

    ######################
    def resourceGiven( self, taskId ):
        if self.waitingForTask:
            #self.resourceManager.updateResource( taskId, resource )
            self.__computeTask( taskId, self.curSrcCode, self.curExtraData, self.curShortDescr )
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
    def resourceRequestRejected( self, taskId, reason ):
        print "Task {} resource request rejected: {}".format( taskId, reason )
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
                    self.__requestTask()

    ######################
    def getProgresses( self ):
        ret = {}
        for c in self.currentComputations:
            tcss = TaskChunkStateSnapshot( c.getTaskId(), 0.0, 0.0, c.getProgress(), c.getTaskShortDescr()  ) #FIXME: cpu power and estimated time left
            ret[ c.taskId ] = tcss

        return ret

    ######################
    def __requestTask( self ):
        self.waitingForTask = self.taskServer.requestTask( self.estimatedPerformance )

    ######################
    def __requestResource( self, taskId, resourceHeader ):
        self.waitingForTask = self.taskServer.requestResource( taskId, resourceHeader )

    ######################
    def __computeTask( self, taskId, srcCode, extraData, shortDescr ):
        self.env.clearTemporary( taskId )
        extraData[ "resourcePath" ] = self.resourceManager.getResourceDir( taskId )
        extraData[ "tmpPath" ] = self.resourceManager.getTemporaryDir( taskId )
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