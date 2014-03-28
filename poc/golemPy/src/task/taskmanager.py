import random

from task import Task

class TaskManager:
    #######################
    def __init__( self ):
        self.tasks = {}
        self.givenTasks = {}

    #######################
    def addNewTask( self, task ):
        assert task.desc.id not in self.tasks
        self.tasks[ task.desc.id ] = task

    #######################
    def getNextSubTask( self, taskId, estimatedPerformance ):
        if taskid in self.tasks:
            task = self.tasks[ taskid ]
            ed = task.queryExtraData( estimatedPerformance )
            if ed:
                self.givenTasks[ [ task, ed ] ] = time.time()
                return taskId, task.codeRes, ed
            else:
                print "Cannot get next task for estimated performence {}".format( estimatedPerformance )
                return 0, "", {}
        else:
            print "Cannot find task {} in my tasks".format( taskId )
            return 0, "", {}

    #######################
    def computedTaskReceived( self, taskId, extraData, result ):
        if taskId in self.tasks:
            self.tasks[ taskId ].computationFinished( extraData, result )
            return True
        else:
            print "It is not my task id {}".format( taskId )
            return False
