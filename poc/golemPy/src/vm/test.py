import sys
sys.path.append('../../testtasks/minilight/src/')

from vm import PythonVM
from task import Task, TaskDescriptor
from resource import PyCodeResource
from twisted.internet import task
from taskdistributor import g_taskDistributor
import time
from twisted.internet import reactor
from multiprocessing import Process, freeze_support
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

testTaskScr2 = """ 
from minilight import render_task
from resource import IntResource

res = render_task( "c:/src/golem/poc/golemPy/testtasks/minilight/cornellbox.ml.txt", startX, startY, width, height, img_width, img_height )


output = IntResource( 1 )
"""

def prepareTasks():
    tasks = []
    n = 0
    while n < 30: 
        td = TaskDescriptor( n, 5, { "g_start" : n * 100000, "g_end" : ( n + 1 ) * 100000 } )

        tasks.append( Task( td, [], PyCodeResource( testTaskScr1 ), 0 ) )
        n += 1

    return tasks

def prepareTasks1( width, height ):
    tasks = []
    n = 0
    for n in range(0, height - 1): 
        td = TaskDescriptor( n, 5, { "startX" : 0 , "startY" : n, "width" : width, "height" : 1, "img_width" : width, "img_height" : height } )

        tasks.append( Task( td, [], PyCodeResource( testTaskScr2 ), 0 ) )
        n += 1

    return tasks

class TaskPerformer( Process ):
    def __init__( self, perfIndex, g_taskDistributor ):
        super(TaskPerformer, self).__init__()
        self.vm = PythonVM()
        self.perfIndex = perfIndex
        self.g_taskDistributor = g_taskDistributor
   
    def run( self ):
        self.doWork()

    def doWork( self ):
        while True:
            t = self.g_taskDistributor.giveTask( self.perfIndex )
            if t:
                self.vm.runTask( t )
                self.g_taskDistributor.acceptTask( t )
            else:
                time.sleep( 0.5 )


def main():
    tasks = prepareTasks1( 10, 10 )
    for t in  tasks:
        g_taskDistributor.appendTask( t )

    tps = []

    for i in range( 4 ):
        #tp = TaskPerformer( random.randrange( 1, 10 ) )
        tp = TaskPerformer( 5, g_taskDistributor )
        #tp.doWork()
        tps.append( tp )
        tp.start()

    for tp in tps:
        tp.join()



if __name__ == '__main__':
    freeze_support()
    main()


