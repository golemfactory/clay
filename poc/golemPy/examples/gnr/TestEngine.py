from TaskState import TaskStatus

from PyQt4 import QtCore

class TestEngine:
    ######################
    def __init__( self, logic ):
        self.tasks      = {}
        self.__setupConnections( logic )

    #####################
    def addTask( self, taskState ):
        from TaskState import TaskState
        assert isinstance( taskState, TaskState )

        if taskState.status != TaskStatus.notStarted:
            print "Wrong task status. Should be {}".format( TaskStatus.notStarted )
            return False

        id = taskState.definition.id

        if id not in self.tasks:
            self.tasks[ id ] = taskState

    #####################
    def __setupConnections( self, logic ):
        QtCore.QObject.connect( logic, QtCore.SIGNAL( "taskStartingRequested(QObject)" ), self.__taskStartingRequested )

    #####################
    def __taskStartingRequested( self, taskState ):

        assert taskState.status == TaskStatus.notStarted # TODO:


        