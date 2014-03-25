from resource import IResource

class TaskManager:
    def __init__( self, server ):
        self.server = server
        self.tasks = {} # TaskDescriptors

    def getTasks( self ):
        return self.tasks.values()

    def addTask( self, taskDict ):
        try:
            id = taskDict[ "id" ]
            if id not in self.tasks.keys():
                self.tasks[ id ] = TaskDescriptor( id, taskDict[ "difficulty" ], taskDict[ "extra" ] )
            return True
        except:
            print "Wrong task received"
            return False


class TaskDescriptor:
    #######################
    def __init__( self, id, difficultyIndex, extraData ):
        self.difficultyIndex = difficultyIndex
        self.id = id
        self.extraData = extraData

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