import logging
import os

from PyQt4.QtGui import QFileDialog
from examples.gnr.ui.VRayDialog import VRayDialog

logger = logging.getLogger(__name__)

class VRayDialogCustomizer:
    #############################
    def __init__( self, gui, logic, newTaskDialog ):
        assert isinstance( gui, VRayDialog )

        self.gui = gui
        self.logic = logic
        self.newTaskDialog = newTaskDialog

        self.rendererOptions = newTaskDialog.rendererOptions

        self.__init()
        self.__setupConnections()

    #############################
    def __init( self ):
        renderer = self.logic.getRenderer( u"VRay" )

    #############################
    def __setupConnections( self ):
        self.gui.ui.buttonBox.rejected.connect( self.gui.window.close )
        self.gui.ui.buttonBox.accepted.connect( lambda: self.__changeRendererOptions() )

    #############################
    def __changeRendererOptions( self ):
        self.newTaskDialog.setRendererOptions( self.rendererOptions )
        self.gui.window.close()
