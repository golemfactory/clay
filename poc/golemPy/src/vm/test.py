import sys
sys.path.append('../../testtasks/minilight/src/')

from vm import PythonVM
from taskbase import Task, TaskDescriptor
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
    call( ["python", "d:/src/golem/poc/golemPy/testtasks/minilight/src/minilight.py", "d:/src/golem/poc/golemPy/testtasks/minilight/cornellbox.ml.txt"] )

foo()

output = IntResource( 1 )
"""

def prepareTasks():
    tasks = []
    n = 0
    while n < 30: 
        td = TaskDescriptor( n, 5, { "g_start" : n * 100000, "g_end" : ( n + 1 ) * 100000 } )

        tasks.append( Task( td, [], testTaskScr1, 0 ) )
        n += 1

    return tasks

def prepareTasks1( width, height ):
    tasks = []
    n = 0
    for n in range(0, height): 
        td = TaskDescriptor( n, 5, { "startX" : 0 , "startY" : n, "width" : width, "height" : 1, "img_width" : width, "img_height" : height } )

        tasks.append( Task( td, [], testTaskScr2, 0 ) )
        n += 1

    return tasks


def main():

    img_width = 10
    img_height = 10
    tasks = prepareTasks1( img_width, img_height )
    for t in  tasks:
        g_taskDistributor.appendTask( t )

    tps = []

    for i in range( 1 ):
        tp = TaskPerformer( 5 )
        #tps.append( tp )
        tp.doWork()
        #tp.start()

    #for tp in tps:
    #    tp.join()


    image_file = open("result.ppm", 'wb')
    image_file.write('%s\n %u %u\n255\n' % ('P6', img_width, img_height))

    for t in reversed( tasks ):
        image_file.write( t.taskResult.read() )

    image_file.close()


if __name__ == '__main__':
    main()


