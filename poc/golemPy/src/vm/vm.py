from resource import IResource
from task import Task

class IGolemVM:
    #######################
    def __init__( self ):
        pass

    #######################
    def addResource( self, resource ):
        pass

    #######################
    def interpret( self, codeResource ):
        pass


class PythonVM( IGolemVM ):
    #######################
    def __init__( self ):
        IGolemVM.__init__( self )
        self.resources = []
        self.codeResource = None
        
    def runTask( self, task ):
        assert isinstance( task, Task )
        self.resources = task.getResources()
        self.codeResource = task.getCode()
        self.scope = task.getExtra()
        task.setResult( self.interpret() )

    #######################
    def interpret( self ):
        res = self.resources
        code = self.codeResource.read()
        exec code in self.scope
        assert isinstance( self.scope[ "output" ], IResource )
        return self.scope[ "output" ]

