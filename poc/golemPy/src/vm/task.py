from resource import IResource
from message import MessageTaskToCompute

from multiprocessing import Process
from twisted.internet import reactor
import random

class TaskManager:
    def __init__( self, server, maxTasksCount = 1 ):
        self.server = server
        self.tasks = {} # TaskDescriptors
        self.maxTasksCount = maxTasksCount
        self.runningTasks = 0
        self.performenceIndex = 10
        self.myTasks = {}
        self.computeSession = None
        self.waitingFotTask = None
        self.currentlyComputedTask = None
        self.currentComputation = None

    def addMyTaskToCompute( self, task ):
        assert isinstance( task, Task )
        assert task.desc.id not in self.myTasks.keys() # trying to add same task again

        self.myTasks[ task.desc.id ] = task

    def getTasks( self ):
        myTasksDesc = []

        for mt in self.myTasks.values:
            myTasksDesc.append( mt.desc )

        return myTasksDesc.append( self.tasks.values() )

    def addTask( self, taskDict ):
        try:
            id = taskDict[ "id" ]
            if id not in self.tasks.keys():
                self.tasks[ id ] = TaskDescriptor( id, taskDict[ "difficulty" ], taskDict[ "extra" ], taskDict[ "address" ], taskDict[ "port" ] )
            return True
        except:
            print "Wrong task received"
            return False

    def chooseTaskWantToCompute( self ):
        if len( self.tasks ) > 0:
            i = random.randrange( 0, len( self.tasks.values() - 1 ) )
            t = self.tasks.values()[ i ]
            return t

    def computeSessionEstablished( self, computeSession ):
        self.computeSession = computeSession

    def giveTask( self, id, perfIndex ):
        if id in self.myTasks:
            task = self.myTasks[ id ]

            if task.needsComputation():
                extraData = task.queryExtraData( perfIndex )
                task.computationStarted( extraData )
                return MessageTaskToCompute( id, extraData, task.getCode().read() )
            else:
                print "Task {} does not need computation yet. Sorry".format( id )

    def taskToComputeReceived( self, task ):
        id = task.taskId

        if self.waitingFotTask.id == id: # We can start computation
            self.currentlyComputedTask = Task( self.waitingFotTask, [], msg.sourceCode, 0 ) # TODO: resources and outputsize handling
            self.waitingFotTask = None
            self.currentComputation = TaskPerformer( self.currentlyComputedTask, self )
            self.currentComputation.start()
            self.currentComputation.join()
            return True

        # We do not wait for this task id
        return False

    def taskComputed( self, task ):
        if task.output:
            print "Task {} computed".format( task.desc.id )

    def runTasks( self ):
        if self.runningTasks < self.maxTasksCount:
            self.waitingFotTask = self.chooseTaskWantToCompute()
            self.server.connectComputeSession( self.waitingFotTask.address, self.waitingFotTask.port )
            self.runningTasks += 1

        if self.computeSession:
            self.computeSession.askForTask( self.waitingFotTask.id, self.performenceIndex )

class TaskDescriptor:
    #######################
    def __init__( self, id, difficultyIndex, extraData, taskOwnerAddress, taskOwnerPort ):
        self.difficultyIndex = difficultyIndex
        self.id = id
        self.extraData = extraData
        self.taskOwnerAddress = taskOwnerAddress
        self.taskOwnerPort = taskOwnerPort

class Task:
    #######################
    def __init__( self, desc, resources, codeRes, outputSize ):
        self.resources = resources
        self.codeRes = codeRes
        self.desc = desc
        self.taskResult = None
        self.outputSize = outputSize

    #######################
    def getResources( self ):
        return self.resources

    #######################
    def getExtra( self ):
        return self.desc.extraData

    #######################
    def getCode( self ):
        return self.codeRes

    def setResult( self, resultRes ):
        self.taskResult = resultRes

    def queryExtraData( self, perfIndex ):
        assert False # Implement in derived class

    def needsComputation( self ):
        assert False # Implement in derived class

    def computationStarted( self, extraData ):
        assert False # Implement in derived class

class RayTracingTask( Task ):
    #######################
    def __init__(self, width, height, desc, resources, codeRes, outputSize):
        super(RayTracingTask, self).__init__(desc, resources, codeRes, outputSize)
        self.width = width
        self.height = height
        self.splitIndex = 0

    def queryExtraData( self, perfIndex ):
        return { "startX" : 0 , "startY" : 0, "width" : width, "height" : height, "img_width" : width, "img_height" : height }

    def needsComputation( self ):
        if self.splitIndex < 5:
            return True
        else:
            return False

    def computationStarted( self, extraData ):
        self.splitIndex += 1


class TaskPerformer( Process ):
    def __init__( self, perfIndex ):
        super( TaskPerformer, self ).__init__()
        self.vm = PythonVM()
        self.task = task
        self.taskManager = taskManager

    def run( self ):
        self.doWork()
        self.taskManager.taskComputed( self.task )

    def doWork( self ):
        self.vm.runTask( self.task )