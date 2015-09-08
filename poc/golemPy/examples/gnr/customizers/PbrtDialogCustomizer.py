import logging
import os
from PyQt4.QtGui import QFileDialog

from examples.gnr.ui.PbrtDialog import PbrtDialog

logger = logging.getLogger(__name__)

class PbrtDialogCustomizer:
    #############################
    def __init__(self, gui, logic, newTaskDialog):

        assert isinstance(gui, PbrtDialog)

        self.gui = gui
        self.logic = logic
        self.newTaskDialog = newTaskDialog
        self.rendererOptions = newTaskDialog.rendererOptions

        self.__init()
        self.__setupConnections()

    #############################
    def __init(self):
        renderer = self.logic.getRenderer(u"PBRT")

        self.gui.ui.pixelFilterComboBox.clear()
        self.gui.ui.pixelFilterComboBox.addItems(self.rendererOptions.filters)
        pixelFilterItem = self.gui.ui.pixelFilterComboBox.findText(self.rendererOptions.pixelFilter)
        if pixelFilterItem >= 0:
            self.gui.ui.pixelFilterComboBox.setCurrentIndex(pixelFilterItem)

        self.gui.ui.pathTracerComboBox.clear()
        self.gui.ui.pathTracerComboBox.addItems(self.rendererOptions.pathTracers)

        algItem = self.gui.ui.pathTracerComboBox.findText(self.rendererOptions.algorithmType)

        if algItem >= 0:
            self.gui.ui.pathTracerComboBox.setCurrentIndex(algItem)

        self.gui.ui.samplesPerPixelSpinBox.setValue(self.rendererOptions.samplesPerPixelCount)

        self.gui.ui.pbrtPathLineEdit.setText(self.rendererOptions.pbrtPath)

    #############################
    def __setupConnections(self):
        self.gui.ui.buttonBox.rejected.connect(self.gui.window.close)
        self.gui.ui.buttonBox.accepted.connect(lambda: self.__changeRendererOptions())
        self.gui.ui.pbrtPathButton.clicked.connect(self.__choosePbrtPath)

    #############################
    def __changeRendererOptions(self):
        self.rendererOptions.pixelFilter = u"{}".format(self.gui.ui.pixelFilterComboBox.itemText(self.gui.ui.pixelFilterComboBox.currentIndex()))
        self.rendererOptions.samplesPerPixelCount = self.gui.ui.samplesPerPixelSpinBox.value()
        self.rendererOptions.algorithmType = u"{}".format(self.gui.ui.pathTracerComboBox.itemText(self.gui.ui.pathTracerComboBox.currentIndex()))
        self.rendererOptions.pbrtPath = u"{}".format(self.gui.ui.pbrtPathLineEdit.text())
        self.newTaskDialog.setRendererOptions(self.rendererOptions)
        self.gui.window.close()

    #############################
    def __choosePbrtPath(self):
        dir = os.path.dirname(u"{}".format(self.gui.ui.pbrtPathLineEdit.text()))
        file_name = u"{}".format(QFileDialog.getOpenFileName(self.gui.window, "Choose pbrt file", dir, ""))
        if file_name != '':
            self.gui.ui.pbrtPathLineEdit.setText(file_name)
