from task import Task
from threading import Lock

TSWaiting   = 0
TSSent      = 1
TSDone      = 2

class TaskDistributor:
    ##########################
    def __init__( self ):
        self.tasks = {}
        self.lock = Lock()
        self.free = []

    ##########################
    def getFreeTasks( self ):
        return self.free

    ##########################
    def giveTask( self, id ):
        if id in self.tasks:
            self.lock.acquire( True )
            if self.tasks[ id ][ "status" ] == TSWaiting:
                self.tasks[ id ][ "status" ] = TSSent
                self.lock.release()
                return self.tasks[ id ][ "task" ]
            else:
                print "Task is done or sent"
                self.lock.release()
                return None
        else:
            print "Cannot find task with id {}".format( id )
            return None

    ##########################
    def acceptTask( self, task ):
        id = task.desc.id
        if id in self.tasks:
            self.lock.acquire( True )
            if self.tasks[ id ][ "status" ] == TSSent:
                if task.taskResult:
                    self.tasks[ id ][ "status" ] = TSDone
                    print "Hurray. Task  {} accepted !!!".format( id )
                else:
                    print "Task not acceped. No output found"
            else:
                print "Haven't sent task with id {}".format( id )
            self.lock.release()
        else:
            print "Cannot find task with id {}. Not accepted !!!".format( id )

    ##########################
    def appendTask( self, task ):
        self.tasks = { task.desc.id : { "task" : task , "status" : TSWaiting } }
        self.free.append( task.desc )

g_taskDistributor = TaskDistributor()