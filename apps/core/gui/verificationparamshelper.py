import logging
from PyQt4 import QtCore

from apps.rendering.task.renderingtaskstate import AdvanceRenderingVerificationOptions

logger = logging.getLogger("gnr.gui")


def read_advance_verification_params(gui, definition):
    if gui.ui.advanceVerificationCheckBox.isChecked():
        definition.verification_options = AdvanceRenderingVerificationOptions()
        if gui.ui.verificationForAllRadioButton.isChecked():
            definition.verification_options.type = 'forAll'
        elif gui.ui.verificationForFirstRadioButton.isChecked():
            definition.verification_options.type = 'forFirst'
        else:
            definition.verification_options.type = 'random'
            try:
                definition.verification_options.probability = float(gui.ui.probabilityLineEdit.text())
                if definition.verification_options.probability < 0:
                    definition.verification_options.probability = 0.0
                    gui.ui.probabilityLineEdit.setText("0.0")
                if definition.verification_options.probability > 1:
                    definition.verification_options.probability = 1.0
                    gui.ui.probabilityLineEdit.setText("1.0")
            except ValueError:
                logger.warning("Wrong probability values {}".format(gui.ui.probabilityLineEdit.text()))
                definition.verification_options.probability = 0.0
                gui.ui.probabilityLineEdit.setText("0.0")
        definition.verification_options.box_size = (int(gui.ui.verificationSizeXSpinBox.value()), int(gui.ui.verificationSizeYSpinBox.value()))
    else:
        definition.verification_options = None

    return definition


def set_verification_widgets_state(gui, state):
    gui.ui.verificationForAllRadioButton.setEnabled(state)
    gui.ui.verificationForFirstRadioButton.setEnabled(state)
    gui.ui.verificationSizeXSpinBox.setEnabled(state)
    gui.ui.verificationSizeYSpinBox.setEnabled(state)
    gui.ui.verificationRandomRadioButton.setEnabled(state)
    gui.ui.probabilityLabel.setEnabled(state and gui.ui.verificationRandomRadioButton.isChecked())
    gui.ui.probabilityLineEdit.setEnabled(state and gui.ui.verificationRandomRadioButton.isChecked())


def load_verification_params(gui, definition):
    enabled = definition.verification_options is not None

    set_verification_widgets_state(gui, enabled)
    if enabled:
        gui.ui.advanceVerificationCheckBox.setCheckState(QtCore.Qt.Checked)
        gui.ui.verificationSizeXSpinBox.setValue(definition.verification_options.box_size[0])
        gui.ui.verificationSizeYSpinBox.setValue(definition.verification_options.box_size[1])
        gui.ui.verificationForAllRadioButton.setChecked(definition.verification_options.type == 'forAll')
        gui.ui.verificationForFirstRadioButton.setChecked(definition.verification_options.type == 'forFirst')
        gui.ui.verificationRandomRadioButton.setChecked(definition.verification_options.type == 'random')
        gui.ui.probabilityLabel.setEnabled(definition.verification_options.type == 'random')
        gui.ui.probabilityLineEdit.setEnabled(definition.verification_options.type == 'random')
        if hasattr(definition.verification_options, 'probability'):
            gui.ui.probabilityLineEdit.setText("{}".format(definition.verification_options.probability))
    else:
        gui.ui.advanceVerificationCheckBox.setCheckState(QtCore.Qt.Unchecked)


def verification_random_changed(gui):
    rand_set = gui.ui.verificationRandomRadioButton.isChecked()
    gui.ui.probabilityLineEdit.setEnabled(rand_set)
    gui.ui.probabilityLabel.setEnabled(rand_set)