
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