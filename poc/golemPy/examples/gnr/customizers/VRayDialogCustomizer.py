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
        self.gui.ui.rtComboBox.addItems( self.rendererOptions.rtEngineValues.values() )
        rtEngineItem = self.gui.ui.rtComboBox.findText( self.rendererOptions.rtEngineValues[ self.rendererOptions.rtEngine ] )
        if rtEngineItem != -1:
            self.gui.ui.rtComboBox.setCurrentIndex( rtEngineItem )
        else:
            logger.error("Wrong renderer type ")

    #############################
    def __setupConnections( self ):
        self.gui.ui.buttonBox.rejected.connect( self.gui.window.close )
        self.gui.ui.buttonBox.accepted.connect( lambda: self.__changeRendererOptions() )

    #############################
    def __changeRendererOptions( self ):
        index = self.gui.ui.rtComboBox.currentIndex()
        rtEngine = u"{}".format( self.gui.ui.rtComboBox.itemText( index ) )
        changed = False
        for key, value in self.rendererOptions.rtEngineValues.iteritems():
            if rtEngine == value:
                self.rendererOptions.rtEngine = key
                self.newTaskDialog.setRendererOptions( self.rendererOptions )
                changed = True
        if not changed:
            logger.error( "Wrong rtEngine value: {}".format( rtEngine ) )
        self.gui.window.close()
