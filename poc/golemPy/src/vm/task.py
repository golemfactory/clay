from resource import PyCodeResource
from message import MessageTaskToCompute, MessageCannotAssignTask
from vm import PythonVM

from threading import Thread
from twisted.internet import reactor
import random
import time

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
        self.dontAskTasks = {}

    def addMyTaskToCompute( self, task ):
        if task:
            assert isinstance( task, Task )
            assert task.desc.id not in self.myTasks.keys() # trying to add same task again

            self.myTasks[ task.desc.id ] = task

        else:
            td = TaskDescriptor( u"231231231", 5, None, "127.0.0.1", self.server.computeListeningPort, 1000 )
            t = RayTracingTask( 10, 10, td )
            self.myTasks[ t.desc.id ] = t

    def getTasks( self ):
        myTasksDesc = []

        for mt in self.myTasks.values():
            if mt.needsComputation():
                myTasksDesc.append( mt.desc )
                print "MY TASK {}".format( mt.desc.id )
                print mt.desc.extraData
                print mt.desc.difficultyIndex

        return myTasksDesc + self.tasks.values()

    def addTask( self, taskDict ):
        try:
            id = taskDict[ "id" ]
            if id not in self.tasks.keys() and id not in self.myTasks.keys():
                print "Adding task {}".format( id )
                self.tasks[ id ] = TaskDescriptor( id, taskDict[ "difficulty" ], taskDict[ "extra" ], taskDict[ "address" ], taskDict[ "port" ], taskDict[ "ttl" ] )
            return True
        except:
            print "Wrong task received"
            return False

    def chooseTaskWantToCompute( self ):
        if len( self.tasks ) > 0:
            i = random.randrange( 0, len( self.tasks.values() ) )
            t = self.tasks.values()[ i ]
            if t.id not in self.dontAskTasks.keys():
                return t
        return None


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
                return MessageCannotAssignTask( id, "Task does not need computation yet. Sorry")
        else:
            return MessageCannotAssignTask( id, "It is not my task")

    def taskToComputeReceived( self, taskMsg ):
        id = taskMsg.taskId

        if self.waitingFotTask.id == id: # We can start computation
            self.currentlyComputedTask = Task( self.waitingFotTask, [], taskMsg.sourceCode, 0 ) # TODO: resources and outputsize handling
            self.waitingFotTask = None
            self.currentlyComputedTask.desc.extraData = taskMsg.extraData
            self.currentComputation = TaskPerformer( self.currentlyComputedTask, self )
            self.currentComputation.start()
            self.currentComputation.join()
            return True

        # We do not wait for this task id
        return False

    def receivedComputedTask( self, id, extraData, taskResult ):
        if id in self.myTasks:
            self.myTasks[ id ].computationFinished( extraData, taskResult )
        else:
            print "Not my task received !!!"


    def taskComputed( self, task ):
        self.runningTasks -= 1
        if task.taskResult:
            print "Task {} computed".format( task.desc.id )
            self.computeSession.sendComputedTask( task.desc.id, task.getExtra(), task.taskResult )

    def runTasks( self ):
        if self.waitingFotTask and self.waitingFotTask.id in self.dontAskTasks.keys():
            self.waitingFotTask = None

        if not self.waitingFotTask and self.runningTasks < self.maxTasksCount:
            self.waitingFotTask = self.chooseTaskWantToCompute()
            if self.waitingFotTask:
                if not self.computeSession:
                    self.server.connectComputeSession( self.waitingFotTask.taskOwnerAddress, self.waitingFotTask.taskOwnerPort )
                self.runningTasks += 1

        if self.computeSession:
            if self.waitingFotTask:
                self.computeSession.askForTask( self.waitingFotTask.id, self.performenceIndex )

    def removeOldTasks( self ):
        for t in self.tasks.values():
            currTime = time.time()
            t.ttl = t.ttl - ( currTime - t.lastChecking )
            t.lastChecking = currTime
            if t.ttl <= 0:
                print "Task {} dies".format( t.id )
                del self.tasks[ t.id ]
                print self.tasks

        for k in self.dontAskTasks.keys():
            if time.time() - self.dontAskTasks[ k ][ "time" ] > 1000:
                del self.dontAskTasks[ k ]

    def stopAsking( self, id, reason ):
        if id not in self.dontAskTasks.keys():
            self.dontAskTasks[ id ] = { "time" : time.time(), "reason" : reason }


class TaskDescriptor:
    #######################
    def __init__( self, id, difficultyIndex, extraData, taskOwnerAddress, taskOwnerPort, ttl ):
        self.difficultyIndex = difficultyIndex
        self.id = id
        self.extraData = extraData
        self.taskOwnerAddress = taskOwnerAddress
        self.taskOwnerPort = taskOwnerPort
        self.lastChecking = time.time()
        self.ttl = ttl

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

    def computationFinished( self, extraData, taskResult ):
        assert False # Implement in derived class

testTaskScr2 = """ 
from minilight import render_task
from resource import ArrayResource
from base64 import encodestring

res = render_task( "d:/src/golem/poc/golemPy/testtasks/minilight/cornellbox.ml.txt", startX, startY, width, height, img_width, img_height )

output = encodestring( res )
"""


class RayTracingTask( Task ):
    #######################
    def __init__( self, width, height, desc ):
        coderes = PyCodeResource( testTaskScr2 )
        Task.__init__( self, desc, [], coderes, 0 )
        self.width = width
        self.height = height
        self.splitIndex = 0

    def queryExtraData( self, perfIndex ):
        return {    "startX" : 0,
                    "startY" : 0,
                    "width" : self.width,
                    "height" : self.height,
                    "img_width" : self.width,
                    "img_height" : self.height }

    def needsComputation( self ):
        if self.splitIndex < 1:
            return True
        else:
            return False

    def computationStarted( self, extraData ):
        self.splitIndex += 1

    def computationFinished( self, extraData, taskResult ):
        print "Receive cumputed task id:{} extraData:{} \n result:{}".format( self.desc.id, extraData, taskResult )

class TaskPerformer( Thread ):
    def __init__( self, task, taskManager ):
        super( TaskPerformer, self ).__init__()
        self.vm = PythonVM()
        self.task = task
        self.taskManager = taskManager

    def run( self ):
        print "RUNNING "
        self.doWork()
        self.taskManager.taskComputed( self.task )

    def doWork( self ):
        self.vm.runTask( self.task )