from vm import PythonVM
from task import Task, TaskDescriptor, TaskOwnerDescriptor
from resource import PyCodeResource
from twisted.internet import task
from taskdistributor import g_taskDistributor
import time
from twisted.internet import reactor
import random

testTaskScr = """ 
from resource import IntResource

def sum( start, end ):
    res = start
    for i in range( start, end ):
        res += i

    return res

output = IntResource( sum( g_start, g_end ) )
"""

def prepareTasks():
    tasks = []
    n = 0
    while n < 100: 
        tod = TaskOwnerDescriptor( "127.0.0.1", 0 )
        td = TaskDescriptor( n, tod, 5, 10 )

        start = "g_start = {} * 10000 \n".format( n )
        end = "g_end = {} * 10000 \n".format( n  + 1 )

        taskSrc = start + end + testTaskScr

        tasks.append( Task( td, [], PyCodeResource( taskSrc ) ) )
        n += 1

    return tasks


class TaskPerformer:
    def __init__( self ):
        self.vm = PythonVM()
        self.workingTask = task.LoopingCall(self.__doWork)
        self.workingTask.start(0.1, False)
   
    def start( self ):
        self.__doWork()

    def __chooseTask( self ):
        if len( self.tasks ) > 1:
            return self.tasks[ random.randrange( 0, len( self.tasks ) - 1 ) ]
        else:
            if len( self.tasks ) == 1:
                return self.tasks[ 0 ]
            else:
                assert False

    def __doWork( self ):
        self.tasks = g_taskDistributor.getFreeTasks()
        if len( self.tasks ) > 0:
            td = self.__chooseTask()
            t = g_taskDistributor.giveTask( td.id )
            if t:
                self.vm.runTask( t )
                g_taskDistributor.acceptTask( t )
            self.tasks = g_taskDistributor.getFreeTasks()
            #if len( self.tasks ) > 0:
            #    self.__doWork()

def main():

    tasks = prepareTasks()
    for t in  tasks:
        g_taskDistributor.appendTask( t )

    for i in range( 5 ):
        tp = TaskPerformer()

    #tp.start()
    reactor.run()

main()