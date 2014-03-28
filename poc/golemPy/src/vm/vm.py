from copy import copy

class IGolemVM:
    #######################
    def __init__( self ):
        pass

    #######################
    def interpret( self, codeResource ):
        pass


class PythonVM( IGolemVM ):
    #######################
    def __init__( self ):
        IGolemVM.__init__( self )
        self.srcCode = ""
        self.scope = {}
      
    #######################  
    def runTask( self, srcCode, extraData ):
        self.srcCode = srcCode
        self.scope = copy( extraData )
        return self.interpret()

    #######################
    def interpret( self ):
        exec self.srcCode in self.scope
        return self.scope[ "output" ]

