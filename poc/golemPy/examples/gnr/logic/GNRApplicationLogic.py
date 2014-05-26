from UiCustomizer import UiCustomizer

class GNRApplicationLogic:
    ######################
    def __init__( self ):
        self.tasks      = {}
        self.customizer = None

    ######################
    def registerGui( self, gui ):
        self.customizer = UiCustomizer( gui, self )

    ######################
    def getTask( self, id ):
        assert id in self.tasks, "GNRApplicationLogic: task {} not added".format( id )

        return self.tasks[ id ]

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
