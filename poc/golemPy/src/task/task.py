from resource import PyCodeResource
from message import MessageTaskToCompute, MessageCannotAssignTask
from vm import PythonVM

from threading import Thread
from twisted.internet import reactor
import random
import time
from img import Img

class TaskManager:
    def __init__( self, server, maxTasksCount = 1 ):
        self.server = server
        self.tasks = {} # TaskDescriptors
        self.maxTasksCount = maxTasksCount
        self.runningTasks = 0
        self.performenceIndex = 1200.0
        self.myTasks = {}
        self.computeSession = None
        self.waitingForTask = None
        self.choosenTaks = None
        self.currentlyComputedTask = None
        self.currentComputation = None
        self.dontAskTasks = {}

    def addMyTaskToCompute( self, task ):
        if task:
            assert isinstance( task, Task )
            assert task.desc.id not in self.myTasks.keys() # trying to add same task again

            self.myTasks[ task.desc.id ] = task

        else:
            hash = random.getrandbits(128)
            td = TaskDescriptor( hash, 5, None, "10.30.10.203", self.server.computeListeningPort, 100000.0 )
            t = VRayTracingTask( 100, 100, 100, td )
            self.myTasks[ t.desc.id ] = t

    def getTasks( self ):
        myTasksDesc = []

        for mt in self.myTasks.values():
            if mt.needsComputation():
                myTasksDesc.append( mt.desc )
                #print "MY TASK {}".format( mt.desc.id )
                #print mt.desc.extraData
                #print mt.desc.difficultyIndex

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

        if not self.waitingForTask:
            print "We do not wait for any task"
            return False

        if self.waitingForTask.id == id: # We can start computation
            self.currentlyComputedTask = Task( self.waitingForTask, [], taskMsg.sourceCode, 0 ) # TODO: resources and outputsize handling
            self.waitingForTask = None
            self.currentlyComputedTask.desc.extraData = taskMsg.extraData
            self.currentComputation = TaskPerformer( self.currentlyComputedTask, self )
            self.currentComputation.start()
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
            if self.computeSession:
                self.computeSession.sendComputedTask( task.desc.id, task.getExtra(), task.taskResult )

    def runTasks( self ):
        if self.currentComputation and self.currentComputation.done:
            self.currentComputation.join()
            self.currentComputation = None

        if self.currentComputation:
            return

        if not self.choosenTaks:
            self.choosenTaks = self.chooseTaskWantToCompute()
            if self.choosenTaks:
                computeSession = self.server.isConnected( self.choosenTaks.taskOwnerAddress, self.choosenTaks.taskOwnerPort )
                if computeSession:
                    self.computeSession.askForTask( self.choosenTaks.id, self.performenceIndex )
                else:
                    self.server.connectComputeSession( self.choosenTaks.taskOwnerAddress, self.choosenTaks.taskOwnerPort )
                
    def removeOldTasks( self ):
        for t in self.tasks.values():
            currTime = time.time()
            t.ttl = t.ttl - ( currTime - t.lastChecking )
            t.lastChecking = currTime
            if t.ttl <= 0:
                print "Task {} dies".format( t.id )
                del self.tasks[ t.id ]
                #print self.tasks

        for k in self.dontAskTasks.keys():
            if time.time() - self.dontAskTasks[ k ][ "time" ] > 1000:
                del self.dontAskTasks[ k ]

    def stopAsking( self, id, reason ):
        if id not in self.dontAskTasks.keys():
            if self.choosenTaks:
                if self.choosenTaks.id == id:
                    self.choosenTaks = None

            if self.waitingForTask:
                if self.waitingForTask.id == id:
                    self.waitingForTask = None

            self.dontAskTasks[ id ] = { "time" : time.time(), "reason" : reason }


class TaskHeader:
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


from taskablerenderer import TaskableRenderer, RenderTaskResult, RenderTaskDesc

TIMESLC  = 10.0
TIMEOUT  = 1000.0

class VRayTracingTask( Task ):
    #######################
    def __init__( self, width, height, num_samples, desc ):

        self.taskableRenderer = TaskableRenderer( width, height, num_samples, None, TIMESLC, TIMEOUT )

        self.w = width
        self.h = height
        self.num_samples = num_samples

        srcFile = open( "../testtasks/minilight/compact_src/renderer.py", "r")
        
        coderes = PyCodeResource( srcFile.read() )
        Task.__init__( self, desc, [], coderes, 0 )

    def queryExtraData( self, perfIndex ):

        taskDesc = self.taskableRenderer.getNextTaskDesc( perfIndex ) 

        return {    "id" : taskDesc.getID(),
                    "x" : taskDesc.getX(),
                    "y" : taskDesc.getY(),
                    "w" : taskDesc.getW(),
                    "h" : taskDesc.getH(),
                    "num_pixels" : taskDesc.getNumPixels(),
                    "num_samples" : taskDesc.getNumSamples(),
                    "subTaskTimeout" : TIMESLC
                    }

    def needsComputation( self ):
        return self.taskableRenderer.hasMoreTasks()

    def computationStarted( self, extraData ):
        pass

    def computationFinished( self, extraData, taskResult ):
        dest = RenderTaskDesc( 0, extraData[ "x" ], extraData[ "y" ], extraData[ "w" ], extraData[ "h" ], extraData[ "num_pixels" ] ,extraData[ "num_samples" ])
        res = RenderTaskResult( dest, taskResult )
        self.taskableRenderer.taskFinished( res )
        if self.taskableRenderer.isFinished():
            VRayTracingTask.__save_image( "ladny.ppm", self.w, self.h, self.taskableRenderer.getResult(), self.num_samples )

    @classmethod
    def __save_image( cls, img_name, w, h, data, num_samples ):
        if not data:
            print "No data to write"
            return False

        img = Img( w, h )
        img.copyPixels( data )

        image_file = open( img_name, 'wb')
        img.get_formatted(image_file, num_samples)
        image_file.close()
