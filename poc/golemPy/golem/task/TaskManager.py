import time

from golem.manager.NodeStateSnapshot import LocalTaskStateSnapshot
from Environment import TaskManagerEnvironment

class TaskManager:
    #######################
    def __init__( self, clientUid, listenAddress = "", listenPort = 0 ):
        self.clientUid      = clientUid
        self.tasks          = {}
        self.tasksComputed  = []
        self.listenAddress  = listenAddress
        self.listenPort     = listenPort

        self.env            = TaskManagerEnvironment( "res", self.clientUid )

        self.subTask2TaskMapping = {}

    #######################
    def addNewTask( self, task):
        assert task.header.taskId not in self.tasks

        task.header.taskOwnerAddress = self.listenAddress
        task.header.taskOwnerPort = self.listenPort

        task.initialize()
        self.tasks[ task.header.taskId ] = task

        self.env.clearTemporary( task.header.taskId )

    #######################
    def getNextSubTask( self, taskId, estimatedPerformance ):
        if taskId in self.tasks:
            task = self.tasks[ taskId ]
            if task.needsComputation():
                ctd  = task.queryExtraData( estimatedPerformance )
                self.subTask2TaskMapping[ ctd.subTaskId ] = taskId
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
            self.tasks[ self.subTask2TaskMapping[ subTaskId ] ].computationFinished( subTaskId, result, self.env )
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
    def prepareResource( self, subTaskId, resourceHeader ):
        if subTaskId in self.subTask2TaskMapping:
            taskId = self.subTask2TaskMapping[ subTaskId ]
            task = self.tasks[ taskId ]
            return task.prepareResourceDelta( subTaskId, taskId, resourceHeader )

    #######################
    def acceptResultsDelay( self, taskId ):
        if taskId in self.tasks:
            return self.tasks[ taskId ].acceptResultsDelay()
        else:
            return -1.0