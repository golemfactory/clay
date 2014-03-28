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
    def getNextTask( self, estimatedPerformance ):
        tasks = self.tasks.values()
        r = range( 0, len( self.tasks.values() ) )

        while len( r ) > 0:
            tn = random.choice( r )
            task = tasks[ tn ]
            ed = task.queryExtraData( estimatedPerformance )
            if ed:
                self.givenTasks[ [ task, ed ] ] = time.time()
                return task, ed
            else:
                r.remove( tn )

        print "Cannot get next task for estimated performence {}".format( estimatedPerformance )
        return None

    #######################
    def computedTaskReceived( self, taskId, extraData, result ):
        if taskId in self.tasks:
            self.tasks[ taskId ].computationFinished( extraData, result )
            return True
        else:
            print "It is not my task id {}".format( taskId )
            return False
