import logging
import os
from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog

from copy import deepcopy

from examples.gnr.ui.PbrtTaskDialog import PbrtTaskDialog
from examples.gnr.task.GNRTask import GNROptions
from VerificationParamsHelper import readAdvanceVerificationParams, setVerificationWidgetsState, loadVerificationParams, \
                                        verificationRandomChanged

logger = logging.getLogger(__name__)

class PbrtTaskDialogCustomizer:
    #############################
    def __init__( self, gui, logic, newTaskDialog ):

        assert isinstance( gui, PbrtTaskDialog )

        self.gui = gui
        self.logic = logic
        self.newTaskDialog = newTaskDialog
        self.options = deepcopy( newTaskDialog.options )

        self.__init()
        self.__setupConnections()

    #############################
    def __init( self ):
        self.__setRendererParameters()
        self.__setOutputParameters()
        self.__setVerificationParameters()

    #############################
    def __setRendererParameters( self ) :
        self.gui.ui.pixelFilterComboBox.clear()
        self.gui.ui.pixelFilterComboBox.addItems( self.options.filters )
        pixelFilterItem = self.gui.ui.pixelFilterComboBox.findText( self.options.pixelFilter )
        if pixelFilterItem >= 0:
            self.gui.ui.pixelFilterComboBox.setCurrentIndex( pixelFilterItem )

        self.gui.ui.pathTracerComboBox.clear()
        self.gui.ui.pathTracerComboBox.addItems( self.options.pathTracers )

        algItem = self.gui.ui.pathTracerComboBox.findText( self.options.algorithmType )

        if algItem >= 0:
            self.gui.ui.pathTracerComboBox.setCurrentIndex( algItem )

        self.gui.ui.samplesPerPixelSpinBox.setValue( self.options.samplesPerPixelCount )

        self.gui.ui.mainSceneLineEdit.setText( self.options.mainSceneFile )

    #############################
    def __setOutputParameters( self ):
        self.gui.ui.outputResXSpinBox.setValue ( self.options.resolution[0] )
        self.gui.ui.outputResYSpinBox.setValue ( self.options.resolution[1] )

        self.gui.ui.outputFormatsComboBox.clear()
        self.gui.ui.outputFormatsComboBox.addItems( self.options.outputFormats )
        for i in range( len( self.options.outputFormats ) ):
            if self.options.outputFormats[ i ] == self.options.outputFormat:
                self.gui.ui.outputFormatsComboBox.setCurrentIndex( i )

        self.gui.ui.outputFileLineEdit.setText( self.options.outputFile )

    #############################
    def __setVerificationParameters( self ):
        loadVerificationParams( self.gui, self.options )

    ############################
    def __setVerificationWidgetsState( self, state ):
        setVerificationWidgetsState( self.gui, state )

    #############################
    def __setupConnections( self ):
        self.gui.ui.cancelButton.clicked.connect( self.gui.window.close )
        self.gui.ui.okButton.clicked.connect( lambda: self.__changeRendererOptions() )
        self.gui.ui.chooseOutputFileButton.clicked.connect( self.__chooseOutputFileButtonClicked )
        self.gui.ui.mainSceneButton.clicked.connect( self.__chooseMainSceneFileButtonClicked )
        QtCore.QObject.connect(self.gui.ui.outputResXSpinBox, QtCore.SIGNAL("valueChanged( const QString )"), self.__resXChanged)
        QtCore.QObject.connect(self.gui.ui.outputResYSpinBox, QtCore.SIGNAL("valueChanged( const QString )"), self.__resYChanged)
        QtCore.QObject.connect(self.gui.ui.verificationRandomRadioButton, QtCore.SIGNAL( "toggled( bool )" ), self.__verificationRandomChanged )
        QtCore.QObject.connect(self.gui.ui.advanceVerificationCheckBox, QtCore.SIGNAL( "stateChanged( int )" ), self.__advanceVerificationChanged )

    #############################
    def __changeRendererOptions( self ):
        self.__readRendererParams()
        self.__readOutputParams()
        self.__readVerificationParams()
        self.newTaskDialog.setOptions( self.options )
        self.gui.window.close()

    #############################
    def __readRendererParams( self ):
        self.options.pixelFilter = u"{}".format( self.gui.ui.pixelFilterComboBox.itemText( self.gui.ui.pixelFilterComboBox.currentIndex() ) )
        self.options.samplesPerPixelCount = self.gui.ui.samplesPerPixelSpinBox.value()
        self.options.algorithmType = u"{}".format( self.gui.ui.pathTracerComboBox.itemText( self.gui.ui.pathTracerComboBox.currentIndex() ) )
        self.options.mainSceneFile = os.path.normpath( u"{}".format( self.gui.ui.mainSceneLineEdit.text() ) )

    #############################
    def __readOutputParams( self ):
        self.options.resolution        = [ self.gui.ui.outputResXSpinBox.value(), self.gui.ui.outputResYSpinBox.value() ]
        self.options.outputFile        = u"{}".format( self.gui.ui.outputFileLineEdit.text() )
        self.options.outputFormat      = u"{}".format( self.gui.ui.outputFormatsComboBox.itemText( self.gui.ui.outputFormatsComboBox.currentIndex() ) )

    #############################
    def __readVerificationParams( self ):
        return readAdvanceVerificationParams( self.gui, self.options )

    #############################
    def __chooseMainSceneFileButtonClicked( self ):
        outputFileTypes = " ".join( [u"*.{}".format( ext ) for ext in self.options.sceneFileExt ] )
        filter = u"Scene files ({})".format( outputFileTypes )


        dir = os.path.dirname( u"{}".format( self.gui.ui.mainSceneLineEdit.text() )  )

        fileName = u"{}".format( QFileDialog.getOpenFileName( self.gui.window,
            "Choose main scene file", dir, filter ) )

        if fileName != '':
            self.gui.ui.mainSceneLineEdit.setText( fileName )


    #############################
    def __chooseOutputFileButtonClicked( self ):
        outputFileType = u"{}".format( self.gui.ui.outputFormatsComboBox.currentText() )
        filter = u"{} (*.{})".format( outputFileType, outputFileType )

        dir = os.path.dirname( u"{}".format( self.gui.ui.outputFileLineEdit.text() )  )

        fileName = u"{}".format( QFileDialog.getSaveFileName( self.gui.window,
            "Choose output file", dir, filter ) )

        if fileName != '':
            self.gui.ui.outputFileLineEdit.setText( fileName )

    #############################
    def __verificationRandomChanged( self ):
        verificationRandomChanged( self.gui )

    #############################
    def __resXChanged( self ):
        self.gui.ui.verificationSizeXSpinBox.setMaximum( self.gui.ui.outputResXSpinBox.value() )

    #############################
    def __resYChanged( self ):
        self.gui.ui.verificationSizeYSpinBox.setMaximum( self.gui.ui.outputResYSpinBox.value() )

    #############################
    def __advanceVerificationChanged( self ):
        state = self.gui.ui.advanceVerificationCheckBox.isChecked()
        self.__setVerificationWidgetsState( state )