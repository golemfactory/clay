from vm import PythonVM
from task import Task, TaskDescriptor
from resource import PyCodeResource
from twisted.internet import task
from taskdistributor import g_taskDistributor
import time
from twisted.internet import reactor
from threading import Thread
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


testTaskScr1 = """ 
from subprocess import call
from resource import IntResource

def foo():
    call( ["python", "c:/src/golem/poc/tasksdep/minilight/src/minilight.py", "c:/src/golem/poc/tasksdep/minilight/cornellbox.ml.txt"] )

foo()

output = IntResource( 1 )
"""

def prepareTasks():
    tasks = []
    n = 0
    while n < 100: 
        td = TaskDescriptor( n, 5, { "g_start" : n * 100000, "g_end" : ( n + 1 ) * 100000 } )

        tasks.append( Task( td, [], PyCodeResource( testTaskScr1 ), 0 ) )
        n += 1

    return tasks


class TaskPerformer( Thread ):
    def __init__( self, perfIndex ):
        super(TaskPerformer, self).__init__()
        self.vm = PythonVM()
        self.perfIndex = perfIndex
   
    def run( self ):
        self.__doWork()

    def __doWork( self ):
        while True:
            t = g_taskDistributor.giveTask( self.perfIndex )
            if t:
                self.vm.runTask( t )
                g_taskDistributor.acceptTask( t )
            else:
                time.sleep( 0.5 )

def main():

    tasks = prepareTasks()
    for t in  tasks:
        g_taskDistributor.appendTask( t )

    tps = []

    for i in range( 4 ):
        #tp = TaskPerformer( random.randrange( 1, 10 ) )
        tp = TaskPerformer( 5 )
        tps.append( tp )
        tp.start()

    for tp in tps:
        tp.join()


main()