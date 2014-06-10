import time

from golem.manager.NodeStateSnapshot import LocalTaskStateSnapshot
from golem.task.TaskState import TaskState, TaskStatus, SubtaskState, ComputerState
from Environment import TaskManagerEnvironment

class TaskManagerEventListener:
    #######################
    def __init__( self ):
        pass

    #######################
    def taskStatusUpdated( self, taskId ):
        pass

class TaskManager:
    #######################
    def __init__( self, clientUid, listenAddress = "", listenPort = 0 ):
        self.clientUid      = clientUid
        self.tasks          = {}
        self.subtaskCurrentlyComputed  = {}
        self.taskComputers  = {}
        self.listenAddress  = listenAddress
        self.listenPort     = listenPort

        self.env            = TaskManagerEnvironment( "res", self.clientUid )

        self.subTask2TaskMapping = {}

        self.listeners      = []

    #######################
    def registerListener( self, listener ):
        assert isinstance( listener, TaskManagerEventListener )

        if listener in self.listeners:
            print "listener {} already registered ".format( listener )
            return

        self.listeners.append( listener )

    #######################
    def unregisterListener( self, listener ):
        for i in range( len( self.listeners ) ):
            if self.listeners[ i ] is listener:
                del self.listeners[ i ]
                return

    #######################
    def addNewTask( self, task ):
        assert task.header.taskId not in self.tasks

        task.header.taskOwnerAddress = self.listenAddress
        task.header.taskOwnerPort = self.listenPort

        task.initialize()
        self.tasks[ task.header.taskId ] = task

        self.env.clearTemporary( task.header.taskId )

        task.taskStatus = TaskStatus.waiting
        self.__noticeTaskUpdated( task.header.taskId )

    #######################
    def getNextSubTask( self, clientId, taskId, estimatedPerformance ):
        if taskId in self.tasks:
            task = self.tasks[ taskId ]
            if task.needsComputation():
                ctd  = task.queryExtraData( estimatedPerformance )
                self.subTask2TaskMapping[ ctd.subTaskId ] = taskId
                self.__appendTaskComputer( taskId, clientId, ctd )

                if taskId not in self.taskComputers:
                    task.taskStatus = TaskStatus.starting
                    self.__noticeTaskUpdated( taskId )
                return ctd
            print "Cannot get next task for estimated performence {}".format( estimatedPerformance )
            return None
        else:
            print "Cannot find task {} in my tasks".format( taskId )
            return None

    #######################
    def getTasksHeaders( self ):
        ret = []
        for t in self.tasks.values():
            if t.needsComputation():
                ret.append( t.header )

        return ret

    #######################
    def computedTaskReceived( self, subTaskId, result ):
        if subTaskId in self.subTask2TaskMapping:
            taskId = self.subTask2TaskMapping[ subTaskId ]
            self.tasks[ taskId ].computationFinished( subTaskId, result, self.env )

            if self.tasks[ taskId ].needsComputation():
                self.tasks[ taskId ].taskStatus = TaskStatus.computing
            else:
                self.tasks[ taskId ].taskStatus = TaskStatus.finished
            self.__noticeTaskUpdated( taskId )

            return True
        else:
            print "It is not my task id {}".format( subTaskId )
            return False

    #######################
    def removeOldTasks( self ):
        for t in self.tasks.values():
            th = t.header
            currTime = time.time()
            th.ttl = th.ttl - ( currTime - th.lastChecking )
            th.lastChecking = currTime
            if th.ttl <= 0:
                print "Task {} dies".format( th.id )
                del self.tasks[ th.id ]

    #######################
    def getProgresses( self ):
        tasksProgresses = {}

        for t in self.tasks.values():
            if t.getProgress() < 1.0:
                ltss = LocalTaskStateSnapshot( t.header.taskId, t.getTotalTasks(), t.getTotalChunks(), t.getActiveTasks(), t.getActiveChunks(), t.getChunksLeft(), t.getProgress(), t.shortExtraDataRepr( 2200.0 ) )
                tasksProgresses[ t.header.taskId ] = ltss

        return tasksProgresses

    #######################
    def prepareResource( self, taskId, resourceHeader ):
        if taskId in self.tasks:
            task = self.tasks[ taskId ]
            return task.prepareResourceDelta( taskId, resourceHeader )

    #######################
    def acceptResultsDelay( self, taskId ):
        if taskId in self.tasks:
            return self.tasks[ taskId ].acceptResultsDelay()
        else:
            return -1.0

    #######################
    def quarryTaskState( self, taskId ):
        if taskId in self.tasks:
            t = self.tasks[ taskId ]
            ret = TaskState()
            ret.status      = t.taskStatus
            ret.progress    = t.getProgress()
            if taskId in self.taskComputers:
                for c in self.taskComputers[ taskId ]:
                    cs = ComputerState()
                    cs.nodeId = c[ 0 ]
                    cs.performance = c[ 1 ].performance
                    cs.subtaskState.subtaskId = c[ 1 ].subTaskId
                    cs.subtaskState.subtaskDefinition = c[ 1 ].shortDescription
                    ret.computers.append( cs )

            ret.timeStarted = t.timeStarted
            ret.elapsedTime = time.time() - ret.timeStarted
            if ret.progress > 0.0:
                ret.remainingTime =  ret.elapsedTime / ret.progress
            else:
                ret.remainingTime = -0.0

            if hasattr( t, "getPreviewFilePath" ): # bardzo brzydkie
                ret.resultPreview = t.getPreviewFilePath()
            return ret
        else:
            assert False, "Should never be here!"
            return None

    #######################
    def __appendTaskComputer( self, taskId, clientId, ctd ):
        if taskId not in self.taskComputers:
            self.taskComputers[ taskId ]        = [ ( clientId, ctd ) ]
            self.tasks[ taskId ].timeStarted    = time.time()
        else:
            self.taskComputers[ taskId ].append( ( clientId, ctd ) )

    #######################
    def __noticeTaskUpdated( self, taskId ):
        for l in self.listeners:
            l.taskStatusUpdated( taskId )