from resource import IResource

class TaskOwnerDescriptor:
    #######################
    def __init__( self, address, port ):
        self.address = address
        self.port = port


class TaskDescriptor:
    #######################
    def __init__( self, id, taskOwner, averageTime, maxTime ):
        self.averageTime = averageTime
        self.id = id
        self.taskOwner = taskOwner
        self.maxTime = maxTime


class Task:
    #######################
    def __init__( self, desc, resources, codeRes ):
        self.resources = resources
        self.codeRes = codeRes
        self.desc = desc
        self.taskResult = None

    #######################
    def getResources( self ):
        return self.resources

    #######################
    def getCode( self ):
        return self.codeRes

    def setResult( self, resultRes ):
        self.taskResult = resultRes