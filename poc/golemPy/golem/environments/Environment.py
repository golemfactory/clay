class Environment:
    @classmethod
    def getId( cls ):
        return "DEFAULT"

    def __init__( self ):
        self.software = []
        self.caps = []

    def checkSoftware( self ):
        return True

    def checkCaps( self ):
        return True

    def supported( self ):
        return True

