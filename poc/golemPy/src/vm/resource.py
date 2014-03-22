
class IResource:
    #######################
    def __init__( self ):
        pass

    #######################
    def read( self ):
        pass

class PyCodeResource( IResource ):
    #######################
    def __init__( self, pyCode ):
        IResource.__init__( self )
        self.pyCode = pyCode

    #######################
    def read( self ):
        return self.pyCode

class IntResource( IResource ):
    def __init__( self, i ):
        IResource.__init__( self )
        self.value = i

    def read( self ):
        return self.value