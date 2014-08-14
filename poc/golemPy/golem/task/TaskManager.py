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

    #######################
    def subtaskStatusUpdated( self, subtaskId ):
        pass


class TaskManager:
    #######################
    def __init__( self, clientUid, listenAddress = "", listenPort = 0 ):
        self.clientUid      = clientUid

        self.tasks          = {}
        self.tasksStates    = {}

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

        ts              = TaskState()
        ts.status       = TaskStatus.waiting
        ts.timeStarted  = time.time()

        self.tasksStates[ task.header.taskId ] = ts

        self.__noticeTaskUpdated( task.header.taskId )

    #######################
    def getNextSubTask( self, clientId, taskId, estimatedPerformance ):
        if taskId in self.tasks:
            task = self.tasks[ taskId ]
            if task.needsComputation():
                ctd  = task.queryExtraData( estimatedPerformance )
                self.subTask2TaskMapping[ ctd.subtaskId ] = taskId
                self.__addSubtaskToTasksStates( clientId, ctd )
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
    def computedTaskReceived( self, subtaskId, result ):
        if subtaskId in self.subTask2TaskMapping:
            taskId = self.subTask2TaskMapping[ subtaskId ]
            self.tasks[ taskId ].computationFinished( subtaskId, result, self.env )
            ss = self.tasksStates[ taskId ].subtaskStates[ subtaskId ]
            ss.subtaskProgress  = 1.0
            ss.subtaskRemTime   = 0.0
            ss.subtaskStatus    = TaskStatus.finished

            if self.tasks[ taskId ].needsComputation():
                self.tasksStates[ taskId ].status = TaskStatus.computing
            else:
                self.tasksStates[ taskId ].status = TaskStatus.finished
            self.__noticeTaskUpdated( taskId )

            return True
        else:
            print "It is not my task id {}".format( subtaskId )
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
    def querryTaskState( self, taskId ):
        if taskId in self.tasksStates and taskId in self.tasks:
            ts  = self.tasksStates[ taskId ]
            t   = self.tasks[ taskId ]

            ts.progress = t.getProgress()
            ts.elapsedTime = time.time() - ts.timeStarted

            if ts.progress > 0.0:
                ts.remainingTime =  ( ts.elapsedTime / ts.progress ) - ts.elapsedTime
            else:
                ts.remainingTime = -0.0

            if hasattr( t, "getPreviewFilePath" ): # bardzo brzydkie
                ts.resultPreview = t.getPreviewFilePath()

            return ts
        else:
            assert False, "Should never be here!"
            return None

    #######################
    def __addSubtaskToTasksStates( self, clientId, ctd ):

        if ctd.taskId not in self.tasksStates:
            assert False, "Should never be here!"
        else:
            ts = self.tasksStates[ ctd.taskId ]

            ss                      = SubtaskState()
            ss.computer.nodeId      = clientId
            ss.computer.performance = ctd.performance
            # TODO: read node ip address
            ss.subtaskDefinition    = ctd.shortDescription
            ss.subtaskId            = ctd.subtaskId
            ss.subtaskStatus        = TaskStatus.starting

            ts.subtaskStates[ ctd.subtaskId ] = ss

    #######################
    def __noticeTaskUpdated( self, taskId ):
        for l in self.listeners:
            l.taskStatusUpdated( taskId )