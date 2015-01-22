import logging
from PyQt4 import QtCore

from examples.gnr.RenderingTaskState import AdvanceRenderingVerificationOptions

logger = logging.getLogger( __name__ )

#############################
def readAdvanceVerificationParams( gui, definition ):
    if gui.ui.advanceVerificationCheckBox.isChecked():
        definition.verificationOptions = AdvanceRenderingVerificationOptions()
        if gui.ui.verificationForAllRadioButton.isChecked():
            definition.verificationOptions.type = 'forAll'
        elif gui.ui.verificationForFirstRadioButton.isChecked():
            definition.verificationOptions.type = 'forFirst'
        else:
            definition.verificationOptions.type = 'random'
            try:
                definition.verificationOptions.probability = float( gui.ui.probabilityLineEdit.text() )
                if definition.verificationOptions.probability < 0:
                    definition.verificationOptions.probability = 0.0
                    gui.ui.probabilityLineEdit.setText( "0.0" )
                if definition.verificationOptions.probability > 1:
                    definition.verificationOptions.probability = 1.0
                    gui.ui.probabilityLineEdit.setText( "1.0" )
            except:
                logger.warning("Wrong probability values {}".format( gui.ui.probabilityLineEdit.text() ) )
                definition.verificationOptions.probability = 0.0
                gui.ui.probabilityLineEdit.setText( "0.0" )
        definition.verificationOptions.boxSize = ( int( gui.ui.verificationSizeXSpinBox.value() ), int( gui.ui.verificationSizeYSpinBox.value() ) )
    else:
        definition.verificationOptions = None

    return definition

#############################
def setVerificationWidgetsState( gui, state ):
    gui.ui.verificationForAllRadioButton.setEnabled( state )
    gui.ui.verificationForFirstRadioButton.setEnabled( state )
    gui.ui.verificationSizeXSpinBox.setEnabled( state )
    gui.ui.verificationSizeYSpinBox.setEnabled( state )
    gui.ui.verificationRandomRadioButton.setEnabled( state )
    gui.ui.probabilityLabel.setEnabled( state and gui.ui.verificationRandomRadioButton.isChecked() )
    gui.ui.probabilityLineEdit.setEnabled( state and gui.ui.verificationRandomRadioButton.isChecked() )
    
def loadVerificationParams( gui, definition ):        
    enabled = definition.verificationOptions is not None

    setVerificationWidgetsState( gui, enabled )
    if enabled:
        gui.ui.advanceVerificationCheckBox.setCheckState( QtCore.Qt.Checked )
        gui.ui.verificationSizeXSpinBox.setValue( definition.verificationOptions.boxSize[0])
        gui.ui.verificationSizeYSpinBox.setValue( definition.verificationOptions.boxSize[1])
        gui.ui.verificationForAllRadioButton.setChecked( definition.verificationOptions.type == 'forAll' )
        gui.ui.verificationForFirstRadioButton.setChecked( definition.verificationOptions.type == 'forFirst' )
        gui.ui.verificationRandomRadioButton.setChecked( definition.verificationOptions.type == 'random' )
        gui.ui.probabilityLabel.setEnabled( definition.verificationOptions.type == 'random')
        gui.ui.probabilityLineEdit.setEnabled( definition.verificationOptions.type == 'random')
        if hasattr( definition.verificationOptions, 'probability' ):
            gui.ui.probabilityLineEdit.setText( "{}".format( definition.verificationOptions.probability ) )
    else:
        gui.ui.advanceVerificationCheckBox.setCheckState( QtCore.Qt.Unchecked )

#############################
def verificationRandomChanged( gui ):
    randSet =  gui.ui.verificationRandomRadioButton.isChecked()
    gui.ui.probabilityLineEdit.setEnabled( randSet )
    gui.ui.probabilityLabel.setEnabled( randSet )