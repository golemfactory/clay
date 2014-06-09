import random
from copy import copy
from multiprocessing import Pool

from PyQt4 import QtCore

from golem.task.TaskBase import Task

class TestEngine( QtCore.QObject ):
    ######################
    def __init__( self, logic ):

        QtCore.QObject.__init__( self )

        self.logic      = logic
        self.tasks      = {}

        QtCore.QObject.connect( logic, QtCore.SIGNAL( "taskStartingRequested(QObject)" ), self.__taskStartingRequested )

    #####################
    def addTask( self, task ):
        assert isinstance( task, Task )

        self.tasks[ task.header.taskId ] = task

        self.__startComputing()

    #####################
    def __startComputing( self ):
        keys = self.tasks.keys()
        r = random.randint( 0, len( keys ) - 1 )

        t = self.tasks[ keys[ r ] ]

        poolSize = 2
        p = Pool( poolSize )

        args = []

        for i in range( poolSize ):
            extraData = t.queryExtraData( 1.0 )
            args.append( [ ( t.srcCode, extraData, None ) ] )

        res = p.map( runTask, args )

        p.start()
        p.join()

        print res

    def __taskStartingRequested( self, ts ):

        tb = self.logic.renderers[ ts.definition.renderer ].taskBuilderType( "client id here", ts.definition )

        t = Task.buildTask( tb )

        self.addTask( t )


#######################
def runTask( srcCode, extraData, progress ):
    extraData = copy( extraData )
    scope = extraData
    scope[ "taskProgress" ] = progress

    exec srcCode in scope
    return scope[ "output" ]

