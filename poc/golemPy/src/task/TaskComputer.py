
import sys
sys.path.append( '../manager')

from threading import Thread, Lock
import time
import os
from copy import copy

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

        self.assignedSubTasks       = {}
        self.curSrcCode             = ""
        self.curExtraData           = None
        self.curShortDescr          = None

    ######################
    def taskGiven( self, subTaskId, srcCode, extraData, shortDescr ):
        if subTaskId not in self.assignedSubTasks:
            self.assignedSubTasks[ subTaskId ] = AssignedSubTask( srcCode, extraData, shortDescr, ownerAddress, ownerPort )

            self.__requestResource( subTaskId, self.resourceManager.getResourceHeader( subTaskId ) )
            return True
        else:
            return False

    ######################
    def resourceGiven( self, subTaskId ):
        if subTaskId in self.assignedSubTasks:
            self.__computeTask( subTaskId, self.assignedSubTasks[ subTaskId ].srcCode, self.assignedSubTasks[ subTaskId ].extraData, self.assignedSubTasks[ subTaskId ].shortDescr )
            return True
        else:
            return False

    ######################
    def taskRequestRejected( self, taskId, reason ):
        print "Task {} request rejected: {}".format( taskId, reason )

    ######################
    def resourceRequestRejected( self, subTaskId, reason ):
        print "Task {} resource request rejected: {}".format( subTaskId, reason )
        del self.assignedSubTasks[ subTaskId ]

    ######################
    def taskComputed( self, taskThread ):
        with self.lock:
            self.currentComputations.remove( taskThread )

            subTaskId   = taskThread.subTaskId

            if taskThread.result:
                print "Task {} computed".format( subTaskId )
                if subTaskId in self.assignedSubTasks:
                    self.taskServer.sendResults( subTaskId, taskThread.result, self.assignedSubTasks[ subTaskId ].ownerAddress, self.assignedSubTasks[ subTaskId ].ownerPort )

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
    def __requestResource( self, subTaskId, resourceHeader ):
        self.waitingForTask = self.taskServer.requestResource( subTaskId, resourceHeader )

    ######################
    def __computeTask( self, subTaskId, srcCode, extraData, shortDescr ):
        self.env.clearTemporary( subTaskId )
        tt = PyTaskThread( self, subTaskId, srcCode, extraData, shortDescr, self.resourceManager.getResourceDir( subTaskId ), self.resourceManager.getTemporaryDir( subTaskId ) ) 
        self.currentComputations.append( tt )
        tt.start()

class AssignedSubTask:
    ######################
    def __init__( self, srcCode, extraData, shortDescr, ownerAddress, ownerPort ):
        self.srcCode        = srcCode
        self.extraData      = extraData
        self.shortDescr     = shortDescr
        self.ownerAddress   = ownerAddress
        self.ownerPort      = ownerPort


class TaskThread( Thread ):
    ######################
    def __init__( self, taskComputer, taskId, srcCode, extraData, shortDescr, resPath, tmpPath ):
        super( TaskThread, self ).__init__()

        self.taskComputer   = taskComputer
        self.vm             = None
        self.taskId         = taskId
        self.srcCode        = srcCode
        self.extraData      = extraData
        self.shortDescr     = shortDescr
        self.result         = None
        self.done           = False
        self.resPath        = resPath
        self.tmpPath        = tmpPath
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
        extraData = copy( self.extraData )
        extraData[ "resourcePath" ] = self.resPath
        extraData[ "tmpPath" ] = self.tmpPath
        self.result = self.vm.runTask( self.srcCode, extraData )


class PyTaskThread( TaskThread ):
    ######################
    def __init__( self, taskComputer, taskId, srcCode, extraData, shortDescr, resPath, tmpPath ):
        super( PyTaskThread, self ).__init__( taskComputer, taskId, srcCode, extraData, shortDescr, resPath, tmpPath )
        self.vm = PythonVM()