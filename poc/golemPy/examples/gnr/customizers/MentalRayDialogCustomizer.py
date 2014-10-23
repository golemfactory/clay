import logging

from examples.gnr.ui.MentalRayDialog import MentalRayDialog

logger = logging.getLogger(__name__)

class MentalRayDialogCustomizer:
    #############################
    def __init__( self, gui, logic, newTaskDialog ):
        assert isinstance( gui, MentalRayDialog )

        self.gui = gui
        self.logic = logic
        self.newTaskDialog = newTaskDialog

        self.__setupConnections()

    #############################
    def __init( self ):
        renderer = self.logic.getRenderer( u"MentalRay" )

    #############################
    def __setupConnections( self ):
        self.gui.ui.buttonBox.rejected.connect( self.gui.window.close )
        self.gui.ui.buttonBox.accepted.connect( lambda: self.__changeRendererOptions() )

    #############################
    def __changeRendererOptions( self ):
        self.gui.window.close()
