from PyQt4 import QtCore

from golem.task.TaskBase import Task

class TestEngine:
    ######################
    def __init__( self, logic ):
        self.tasks      = {}

    #####################
    def addTask( self, task ):
        assert isinstance( task, Task )

        self.tasks[ task.header.taskId ] = task



