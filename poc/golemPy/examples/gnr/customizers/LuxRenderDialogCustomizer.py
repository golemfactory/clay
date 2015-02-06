import logging
from PyQt4 import QtCore
from PyQt4.QtGui import QMessageBox

from golem.environments.Environment import Environment

from examples.gnr.ui.LuxRenderDialog import LuxRenderDialog
from examples.gnr.RenderingEnvironment import LuxRenderEnvironment

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
        if self.rendererOptions.sendBinaries:
            self.gui.ui.sendLuxRadioButton.toggle()
        else:
            self.gui.ui.useInstalledRadioButton.toggle()
        self.gui.ui.luxConsoleLineEdit.setEnabled( self.rendererOptions.sendBinaries )
        self.gui.ui.luxConsoleLineEdit.setText( u"{}".format( self.rendererOptions.luxconsole ))

    #############################
    def __setupConnections( self ):
        self.gui.ui.cancelButton.clicked.connect( self.gui.close )
        self.gui.ui.okButton.clicked.connect( lambda: self.__changeRendererOptions() )
        QtCore.QObject.connect(self.gui.ui.sendLuxRadioButton, QtCore.SIGNAL( "toggled( bool )" ), self.__sendLuxSettingsChanged )

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

        self.rendererOptions.sendBinaries = self.gui.ui.sendLuxRadioButton.isChecked()
        self.rendererOptions.luxconsole = u"{}".format( self.gui.ui.luxConsoleLineEdit.text() )

        if self.rendererOptions.sendBinaries:
            self.rendererOptions.environment = Environment()
        else:
            self.rendererOptions.environment = LuxRenderEnvironment()

        self.newTaskDialog.setRendererOptions( self.rendererOptions )
        self.gui.window.close()

    #############################
    def __sendLuxSettingsChanged( self ):
        self.gui.ui.luxConsoleLineEdit.setEnabled( self.gui.ui.sendLuxRadioButton.isChecked() )