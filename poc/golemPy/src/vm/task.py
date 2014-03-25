from resource import IResource
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
        self.currentlyComputedTask = None

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

    def runTasks( self ):
        if self.runningTasks < self.maxTasksCount:
            self.currentlyComputedTask = self.chooseTaskWantToCompute()
            self.server.connectComputeSession( self.currentlyComputedTask.address, self.currentlyComputedTask.port )
            self.runningTasks += 1

        if self.computeSession:
            self.computeSession.askForTask( self.currentlyComputedTask.id, self.performenceIndex )

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