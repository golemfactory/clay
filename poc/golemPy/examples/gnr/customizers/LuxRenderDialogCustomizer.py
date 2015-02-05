import logging

from PyQt4 import QtCore
from PyQt4.QtGui import QMessageBox
from examples.gnr.ui.LuxRenderDialog import LuxRenderDialog

logger = logging.getLogger(__name__)

class LuxRenderDialogCustomizer:
    #############################
    def __init__( self, gui, logic, newTaskDialog ):
        assert isinstance( gui, LuxRenderDialog )

        self.gui = gui
        self.logic = logic
        self.newTaskDialog = newTaskDialog

        self.rendererOptions = newTaskDialog.rendererOptions

        self.__init()
        self.__setupConnections()

    #############################
    def __init( self ):
        renderer = self.logic.getRenderer( u"LuxRender" )
        self.gui.ui.haltTimeLineEdit.setText( u"{}".format( self.rendererOptions.halttime ) )
        self.gui.ui.haltsppLineEdit.setText( u"{}".format( self.rendererOptions.haltspp ) )

    #############################
    def __setupConnections( self ):
        self.gui.ui.cancelButton.clicked.connect( self.gui.close )
        self.gui.ui.okButton.clicked.connect( lambda: self.__changeRendererOptions() )

    #############################
    def __changeRendererOptions( self ):
        try:
            self.rendererOptions.halttime = int( self.gui.ui.haltTimeLineEdit.text() )
        except ValueError:
            logger.error( "{} is not proper halttime value".format( self.gui.ui.haltTimeLineEdit.text() ) )
        try:
            self.rendererOptions.haltspp = int( self.gui.ui.haltsppLineEdit.text() )
        except ValueError:
            logger.error("{} in not proper haltspp value".format( self.gui.ui.haltsppLineEdit.text()) )

        self.newTaskDialog.setRendererOptions( self.rendererOptions )
        self.gui.window.close()
