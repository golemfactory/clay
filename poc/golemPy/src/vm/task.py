from resource import IResource


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