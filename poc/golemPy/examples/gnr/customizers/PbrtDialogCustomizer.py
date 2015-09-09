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
        self.renderer_options = newTaskDialog.renderer_options

        self.__init()
        self.__setup_connections()

    #############################
    def __init(self):
        renderer = self.logic.get_renderer(u"PBRT")

        self.gui.ui.pixelFilterComboBox.clear()
        self.gui.ui.pixelFilterComboBox.addItems(self.renderer_options.filters)
        pixel_filterItem = self.gui.ui.pixelFilterComboBox.findText(self.renderer_options.pixel_filter)
        if pixel_filterItem >= 0:
            self.gui.ui.pixelFilterComboBox.setCurrentIndex(pixel_filterItem)

        self.gui.ui.pathTracerComboBox.clear()
        self.gui.ui.pathTracerComboBox.addItems(self.renderer_options.path_tracers)

        algItem = self.gui.ui.pathTracerComboBox.findText(self.renderer_options.algorithm_type)

        if algItem >= 0:
            self.gui.ui.pathTracerComboBox.setCurrentIndex(algItem)

        self.gui.ui.samplesPerPixelSpinBox.setValue(self.renderer_options.samples_per_pixel_count)

        self.gui.ui.pbrtPathLineEdit.setText(self.renderer_options.pbrt_path)

    #############################
    def __setup_connections(self):
        self.gui.ui.buttonBox.rejected.connect(self.gui.window.close)
        self.gui.ui.buttonBox.accepted.connect(lambda: self.__changeRendererOptions())
        self.gui.ui.pbrtPathButton.clicked.connect(self.__choosePbrtPath)

    #############################
    def __changeRendererOptions(self):
        self.renderer_options.pixel_filter = u"{}".format(self.gui.ui.pixelFilterComboBox.itemText(self.gui.ui.pixelFilterComboBox.currentIndex()))
        self.renderer_options.samples_per_pixel_count = self.gui.ui.samplesPerPixelSpinBox.value()
        self.renderer_options.algorithm_type = u"{}".format(self.gui.ui.pathTracerComboBox.itemText(self.gui.ui.pathTracerComboBox.currentIndex()))
        self.renderer_options.pbrt_path = u"{}".format(self.gui.ui.pbrtPathLineEdit.text())
        self.newTaskDialog.setRendererOptions(self.renderer_options)
        self.gui.window.close()

    #############################
    def __choosePbrtPath(self):
        dir = os.path.dirname(u"{}".format(self.gui.ui.pbrtPathLineEdit.text()))
        file_name = u"{}".format(QFileDialog.getOpenFileName(self.gui.window, "Choose pbrt file", dir, ""))
        if file_name != '':
            self.gui.ui.pbrtPathLineEdit.setText(file_name)
