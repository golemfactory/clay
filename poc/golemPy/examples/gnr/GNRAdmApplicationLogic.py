import os
import glob
import uuid
import logging
import cPickle as pickle

from golem.task.TaskState import TaskStatus
from golem.task.TaskBase import Task

from examples.gnr.task.InfoTask import InfoTaskBuilder, InfoTaskDefinition
from examples.gnr.task.UpdateOtherGolemsTask import UpdateOtherGolemsTaskBuilder, UpdateOtherGolemsTaskDefinition

from GNRApplicationLogic import GNRApplicationLogic

logger = logging.getLogger(__name__)

class GNRAdmApplicationLogic( GNRApplicationLogic ):
    ######################
    def __init__( self ):
        GNRApplicationLogic.__init__( self )
        self.startNodesManagerFunction = lambda: None

    ######################
    def registerStartNodesManagerFunction( self, func ):
        self.startNodesManagerFunction = func

    ######################
    def startNodesManagerServer( self ):
        self.startNodesManagerFunction()

    ######################
    def sendTestTasks( self ):
        path = os.path.join( os.environ.get( 'GOLEM' ), 'save/test')
        files = glob.glob( os.path.join( path, '*.gt' ) )
        tasks = []
        for file_ in files:
            taskState = self._getNewTaskState()
            taskState.status = TaskStatus.notStarted
            taskState.definition = pickle.loads( open( file_, 'r' ).read() )
            import uuid
            taskState.definition.taskId = "{}".format( uuid.uuid4() )
            tasks.append( taskState )
        self.addTasks ( tasks )
        for task in tasks:
            self.startTask( task.definition.taskId )

    ######################
    def updateOtherGolems( self, golemDir ):
        taskDefinition         = UpdateOtherGolemsTaskDefinition()
        taskDefinition.taskId  = "{}".format( uuid.uuid4() )
        taskDefinition.srcFile          = os.path.join( os.environ.get('GOLEM'), "examples\\tasks\\updateGolem.py" )
        taskDefinition.totalSubtasks    = 100
        taskDefinition.fullTaskTimeout  = 4 * 60 * 60
        taskDefinition.subtaskTimeout   = 20 * 60

        taskBuilder = UpdateOtherGolemsTaskBuilder( self.client.getId(),
                                          taskDefinition,
                                        self.client.getRootPath(), golemDir )

        task = Task.buildTask(  taskBuilder )
        self.addTaskFromDefinition( taskDefinition )
        self.client.enqueueNewTask( task )

        logger.info( "Update with {}".format( golemDir ) )


    ######################
    def sendInfoTask( self, iterations, fullTaskTimeout, subtaskTimeout ):
        infoTaskDefinition = InfoTaskDefinition()
        infoTaskDefinition.taskId           = "{}".format( uuid.uuid4() )
        infoTaskDefinition.srcFile          = os.path.join( os.environ.get('GOLEM'), "examples\\tasks\\sendSnapshot.py" )
        infoTaskDefinition.totalSubtasks    = iterations
        infoTaskDefinition.fullTaskTimeout  = fullTaskTimeout
        infoTaskDefinition.subtaskTimeout   = subtaskTimeout
        infoTaskDefinition.managerAddress   = self.client.configDesc.managerAddress
        infoTaskDefinition.managerPort      = self.client.configDesc.managerPort

        taskBuilder = InfoTaskBuilder( self.client.getId(),
                                          infoTaskDefinition,
                                        self.client.getRootPath() )

        task = Task.buildTask(  taskBuilder )
        self.addTaskFromDefinition( infoTaskDefinition )
        self.client.enqueueNewTask( task )
