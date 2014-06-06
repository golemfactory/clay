from threading import Lock

class IGolemVM:
    #######################
    def __init__( self ):
        pass

    #######################
    def getProgress( self ):
        assert False

    #######################
    def interpret( self, codeResource ):
        pass


class TaskProgress:
    #######################
    def __init__( self ):
        self.lock = Lock()
        self.progress = 0.0

    #######################
    def get( self ):
        with self.lock:
            return self.progress

    #######################
    def set( self, val ):
        with self.lock:
            self.progress = val


class PythonVM( IGolemVM ):
    #######################
    def __init__( self ):
        IGolemVM.__init__( self )
        self.srcCode = ""
        self.scope = {}
        self.progress = TaskProgress()

    #######################
    def getProgress( self ):
        return self.progress.get()
      
    #######################  
    def runTask( self, srcCode, extraData ):
        self.srcCode = srcCode
        self.scope = extraData
        self.scope[ "taskProgress" ] = self.progress
        return self.__interpret()

    #######################
    def __interpret( self ):
        exec self.srcCode in self.scope
        return self.scope[ "output" ]
