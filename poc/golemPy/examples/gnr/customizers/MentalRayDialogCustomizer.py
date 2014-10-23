import logging
import os

from PyQt4.QtGui import QFileDialog
from examples.gnr.ui.MentalRayDialog import MentalRayDialog

logger = logging.getLogger(__name__)

class MentalRayDialogCustomizer:
    #############################
    def __init__( self, gui, logic, newTaskDialog ):
        assert isinstance( gui, MentalRayDialog )

        self.gui = gui
        self.logic = logic
        self.newTaskDialog = newTaskDialog

        self.rendererOptions = newTaskDialog.getRendererOptions()
        self.__init()
        self.__setupConnections()

    #############################
    def __init( self ):
        renderer = self.logic.getRenderer( u"MentalRay" )
        self.gui.ui.presetLineEdit.setText( self.rendererOptions.preset )

    #############################
    def __setupConnections( self ):
        self.gui.ui.buttonBox.rejected.connect( self.gui.window.close )
        self.gui.ui.buttonBox.accepted.connect( lambda: self.__changeRendererOptions() )
        self.gui.ui.presetButton.clicked.connect( self.__choosePresetFile )

    #############################
    def __changeRendererOptions( self ):
        self.rendererOptions.preset = u"{}".format( self.gui.ui.presetLineEdit.text() )
        self.newTaskDialog.setRendererOptions( self.rendererOptions )
        self.gui.window.close()

    #############################
    def __choosePresetFile( self ):
        dir = os.path.dirname( u"{}".format( self.gui.ui.presetLineEdit.text() ) )
        presetFile = u"{}".format( QFileDialog.getOpenFileName( self.gui.window, "Choose preset file", dir, "3dsMax render preset file (*.rps)") )
        if presetFile != '':
            self.gui.ui.presetLineEdit.setText ( presetFile )