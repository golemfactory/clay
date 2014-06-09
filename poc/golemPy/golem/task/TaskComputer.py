
import sys
sys.path.append( '../manager')

from threading import Thread, Lock
import time
from copy import copy

from golem.vm.vm import PythonVM
from golem.manager.NodeStateSnapshot import TaskChunkStateSnapshot
from golem.task.resource.ResourcesManager import ResourcesManager
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
        self.taskToSubTaskMapping   = {}
        self.maxAssignedTasks       = 1
        self.curSrcCode             = ""
        self.curExtraData           = None
        self.curShortDescr          = None

    ######################
    def taskGiven( self, ctd ):
        if ctd.subTaskId not in self.assignedSubTasks:
            self.assignedSubTasks[ ctd.subTaskId ] = ctd
            self.taskToSubTaskMapping[ ctd.taskId ] = ctd.subTaskId
            self.__requestResource( ctd.taskId, self.resourceManager.getResourceHeader( ctd.taskId ), ctd.returnAddress, ctd.returnPort )
            return True
        else:
            return False

    ######################
    def resourceGiven( self, taskId ):
        if taskId in self.taskToSubTaskMapping:
            subtaskId = self.taskToSubTaskMapping[ taskId ]
            if subtaskId in self.assignedSubTasks:
                self.__computeTask( subtaskId, self.assignedSubTasks[ subtaskId ].srcCode, self.assignedSubTasks[ subtaskId ].extraData, self.assignedSubTasks[ subtaskId ].shortDescription )
                self.waitingForTask = None
                return True
            else:
                return False

    ######################
    def taskRequestRejected( self, taskId, reason ):
        self.waitingForTask = None
        print "Task {} request rejected: {}".format( taskId, reason )

    ######################
    def resourceRequestRejected( self, subTaskId, reason ):
        self.waitingForTask = None
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
                    self.taskServer.sendResults( subTaskId, taskThread.result, self.assignedSubTasks[ subTaskId ].returnAddress, self.assignedSubTasks[ subTaskId ].returnPort )
                    del self.assignedSubTasks[ subTaskId ]

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
            tcss = TaskChunkStateSnapshot( c.getSubTaskId(), 0.0, 0.0, c.getProgress(), c.getTaskShortDescr()  ) #FIXME: cpu power and estimated time left
            ret[ c.subTaskId ] = tcss

        return ret

    ######################
    def __requestTask( self ):
        self.waitingForTask = self.taskServer.requestTask( self.estimatedPerformance )

    ######################
    def __requestResource( self, taskId, resourceHeader, returnAddress, returnPort ):
        self.waitingForTask = self.taskServer.requestResource( taskId, resourceHeader, returnAddress, returnPort )

    ######################
    def __computeTask( self, subtaskId, srcCode, extraData, shortDescr ):
        taskId = self.assignedSubTasks[ subtaskId ].taskId
        self.env.clearTemporary( taskId )
        tt = PyTaskThread( self, subtaskId, srcCode, extraData, shortDescr, self.resourceManager.getResourceDir( taskId ), self.resourceManager.getTemporaryDir( taskId ) )
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
    def __init__( self, taskComputer, subTaskId, srcCode, extraData, shortDescr, resPath, tmpPath ):
        super( TaskThread, self ).__init__()

        self.taskComputer   = taskComputer
        self.vm             = None
        self.subTaskId      = subTaskId
        self.srcCode        = srcCode
        self.extraData      = extraData
        self.shortDescr     = shortDescr
        self.result         = None
        self.done           = False
        self.resPath        = resPath
        self.tmpPath        = tmpPath
        self.lock           = Lock()

    ######################
    def getSubTaskId( self ):
        return self.subTaskId

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
    def __init__( self, taskComputer, subTaskId, srcCode, extraData, shortDescr, resPath, tmpPath ):
        super( PyTaskThread, self ).__init__( taskComputer, subTaskId, srcCode, extraData, shortDescr, resPath, tmpPath )
        self.vm = PythonVM()