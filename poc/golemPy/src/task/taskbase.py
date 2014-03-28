import time

class TaskHeader:
    #######################
    def __init__( self, id, taskOwnerAddress, taskOwnerPort, ttl = 0.0 ):
        self.id = id
        self.taskOwnerAddress = taskOwnerAddress
        self.taskOwnerPort = taskOwnerPort
        self.lastChecking = time.time()
        self.ttl = ttl

class Task:
    #######################
    def __init__( self, header, resources, codeRes, outputSize ):
        self.resources = resources
        self.codeRes = codeRes
        self.header = header
        self.taskResult = None
        self.outputSize = outputSize

    #######################
    def getResources( self ):
        return self.resources

    #######################
    def getExtra( self ):
        return self.taskHeader.extraData

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


#class TaskManager:
#    def __init__( self, server, maxTasksCount = 1 ):
#        self.server = server
#        self.tasks = {} # TaskDescriptors
#        self.maxTasksCount = maxTasksCount
#        self.runningTasks = 0
#        self.performenceIndex = 1200.0
#        self.myTasks = {}
#        self.computeSession = None
#        self.waitingForTask = None
#        self.choosenTaks = None
#        self.currentlyComputedTask = None
#        self.currentComputation = None
#        self.dontAskTasks = {}

#    def addMyTaskToCompute( self, task ):
#        if task:
#            assert isinstance( task, Task )
#            assert task.taskHeader.id not in self.myTasks.keys() # trying to add same task again

#            self.myTasks[ task.taskHeader.id ] = task

#        else:
#            hash = random.getrandbits(128)
#            td = TaskDescriptor( hash, 5, None, "10.30.10.203", self.server.computeListeningPort, 100000.0 )
#            t = VRayTracingTask( 100, 100, 100, td )
#            self.myTasks[ t.taskHeader.id ] = t

#    def getTasks( self ):
#        myTasksDesc = []

#        for mt in self.myTasks.values():
#            if mt.needsComputation():
#                myTasksDesc.append( mt.taskHeader )
#                #print "MY TASK {}".format( mt.taskHeader.id )
#                #print mt.taskHeader.extraData
#                #print mt.taskHeader.difficultyIndex

#        return myTasksDesc + self.tasks.values()

#    def addTask( self, taskDict ):
#        try:
#            id = taskDict[ "id" ]
#            if id not in self.tasks.keys() and id not in self.myTasks.keys():
#                print "Adding task {}".format( id )
#                self.tasks[ id ] = TaskDescriptor( id, taskDict[ "difficulty" ], taskDict[ "extra" ], taskDict[ "address" ], taskDict[ "port" ], taskDict[ "ttl" ] )
#            return True
#        except:
#            print "Wrong task received"
#            return False

#    def chooseTaskWantToCompute( self ):
#        if len( self.tasks ) > 0:
#            i = random.randrange( 0, len( self.tasks.values() ) )
#            t = self.tasks.values()[ i ]
#            if t.id not in self.dontAskTasks.keys():
#                return t
#        return None


#    def computeSessionEstablished( self, computeSession ):
#        self.computeSession = computeSession

#    def giveTask( self, id, perfIndex ):
#        if id in self.myTasks:
#            task = self.myTasks[ id ]

#            if task.needsComputation():
#                extraData = task.queryExtraData( perfIndex )
#                task.computationStarted( extraData )
#                return MessageTaskToCompute( id, extraData, task.getCode().read() )
#            else:
#                return MessageCannotAssignTask( id, "Task does not need computation yet. Sorry")
#        else:
#            return MessageCannotAssignTask( id, "It is not my task")

#    def taskToComputeReceived( self, taskMsg ):
#        id = taskMsg.taskId

#        if not self.waitingForTask:
#            print "We do not wait for any task"
#            return False

#        if self.waitingForTask.id == id: # We can start computation
#            self.currentlyComputedTask = Task( self.waitingForTask, [], taskMsg.sourceCode, 0 ) # TODO: resources and outputsize handling
#            self.waitingForTask = None
#            self.currentlyComputedTask.taskHeader.extraData = taskMsg.extraData
#            self.currentComputation = TaskPerformer( self.currentlyComputedTask, self )
#            self.currentComputation.start()
#            return True

#        # We do not wait for this task id
#        return False

#    def receivedComputedTask( self, id, extraData, taskResult ):
#        if id in self.myTasks:
#            self.myTasks[ id ].computationFinished( extraData, taskResult )
#        else:
#            print "Not my task received !!!"


#    def taskComputed( self, task ):
#        self.runningTasks -= 1
#        if task.taskResult:
#            print "Task {} computed".format( task.taskHeader.id )
#            if self.computeSession:
#                self.computeSession.sendComputedTask( task.taskHeader.id, task.getExtra(), task.taskResult )

#    def runTasks( self ):
#        if self.currentComputation and self.currentComputation.done:
#            self.currentComputation.join()
#            self.currentComputation = None

#        if self.currentComputation:
#            return

#        if not self.choosenTaks:
#            self.choosenTaks = self.chooseTaskWantToCompute()
#            if self.choosenTaks:
#                computeSession = self.server.isConnected( self.choosenTaks.taskOwnerAddress, self.choosenTaks.taskOwnerPort )
#                if computeSession:
#                    self.computeSession.askForTask( self.choosenTaks.id, self.performenceIndex )
#                else:
#                    self.server.connectComputeSession( self.choosenTaks.taskOwnerAddress, self.choosenTaks.taskOwnerPort )
                

#    def stopAsking( self, id, reason ):
#        if id not in self.dontAskTasks.keys():
#            if self.choosenTaks:
#                if self.choosenTaks.id == id:
#                    self.choosenTaks = None

#            if self.waitingForTask:
#                if self.waitingForTask.id == id:
#                    self.waitingForTask = None

#            self.dontAskTasks[ id ] = { "time" : time.time(), "reason" : reason }