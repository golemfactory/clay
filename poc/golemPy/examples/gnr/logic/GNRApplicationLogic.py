from MainWindowCustomizer import MainWindowCustomizer

class GNRApplicationLogic:
    ######################
    def __init__( self ):
        self.tasks              = {}
        self.renderers          = {}
        self.testTasks          = {}
        self.customizer         = None
        self.currentRenderer    = None

    ######################
    def registerGui( self, gui ):
        self.customizer = MainWindowCustomizer( gui, self )

    ######################
    def getTask( self, id ):
        assert id in self.tasks, "GNRApplicationLogic: task {} not added".format( id )

        return self.tasks[ id ]

    ######################
    def getRenderers( self ):
        return self.renderers

    ######################
    def getRenderer( self, name ):
        if name in self.renderers:
            return self.renderers[ name ]
        else:
            assert False, "Renderer {} not registered".format( name )

    ######################
    def getTestTasks( self ):
        return self.testTasks

    ######################
    def addTasks( self, tasks ):

        if len( tasks ) == 0:
            return

        for t in tasks:
            if t.id not in self.tasks:
                self.tasks[ t.id ] = t
                self.customizer.addTask( t )
            else:
                self.tasks[ t.id ] = t

        self.customizer.updateTasks( self.tasks )

    ######################
    def registerNewRendererType( self, renderer ):
        if renderer.name not in self.renderers:
            self.renderers[ renderer.name ] = renderer
        else:
            assert False, "Renderer {} already registered".format( renderer.name )

    ######################
    def registerNewTestTaskType( self, testTaskInfo ):
        if testTaskInfo.name not in self.testTasks:
            self.testTasks[ testTaskInfo.name ] = testTaskInfo
        else:
            assert False, "Test task {} already registered".format( testTaskInfo.name )

    ######################
    def setCurrentRenderer( self, rname ):
        if rname in self.renderers:
            self.currentRenderer = self.renderers[ rname ]
        else:
            assert False, "Unreachable"

    ######################
    def getCurrentRenderer( self ):
        return self.currentRenderer

    ######################
    def runTestTask( self, taskState ):
        return True
