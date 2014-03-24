from task import Task
from multiprocessing import Lock

TSWaiting   = 0
TSSent      = 1
TSDone      = 2

class TaskInfo:
    def __init__( self, task, status ):
        self.task = task
        self.status = status


class TaskDistributor:
    ##########################
    def __init__( self ):
        self.tasks = {}
        self.tasksID = {}
        self.lock = Lock()

    ##########################
    def giveTask( self, nodePerformence ):
        with self.lock:
            t = self.__findTask( nodePerformence )
            if t:
                t.status = TSSent
                return t.task
            else:
                print "No task for you. Sorry"
                return None

    ##########################
    def acceptTask( self, task ):
        id = task.desc.id
        if id in self.tasksID.keys():
            with self.lock:
                if self.tasksID[ id ].status == TSSent:
                    if task.taskResult:
                        self.tasksID[ id ].status = TSDone
                        print "Hurray. Task  {} accepted !!!".format( id )
                    else:
                        print "Task not acceped. No output found"
                else:
                    print "Haven't sent task with id {}".format( id )
        else:
            print "Cannot find task with id {}. Not accepted !!!".format( id )

    ##########################
    def appendTask( self, task ):
        diffIndex = task.desc.difficultyIndex
        taskInfo = TaskInfo( task, TSWaiting )
        if diffIndex in self.tasks.keys():
            self.tasks[ diffIndex ].append( taskInfo )
        else:
            self.tasks[ diffIndex ] = [ taskInfo ]

        self.tasksID[ task.desc.id ] = taskInfo

        print "Append task {}".format( task.desc.id )

    ##########################
    def __findTask( self, index ):
        sorted = self.tasks.keys().sort()
        sorted = self.tasks.keys()
        i = 0
        diff = 0
        while i < len( sorted ):
            if sorted[ i ] >= index:
                break
            i += 1

        if i >= len( sorted ):
            return None

        t = self.tasks[ sorted[ i ] ]
        
        i = 0
        while i < len( t ) and t[ i ].status != TSWaiting:
            i += 1

        if i < len( t ):
            return t[ i ]
        else:
            return None



g_taskDistributor = TaskDistributor()