import logging
import os
from PyQt4.QtGui import QFileDialog

from gnr.customizers.renderercustomizer import RendererCustomizer


logger = logging.getLogger(__name__)


class PbrtDialogCustomizer(RendererCustomizer):

    def load_data(self):
        renderer = self.logic.get_renderer(u"PBRT")

        self.gui.ui.pixelFilterComboBox.clear()
        self.gui.ui.pixelFilterComboBox.addItems(self.renderer_options.filters)
        pixel_filter_item = self.gui.ui.pixelFilterComboBox.findText(self.renderer_options.pixel_filter)
        if pixel_filter_item >= 0:
            self.gui.ui.pixelFilterComboBox.setCurrentIndex(pixel_filter_item)

        self.gui.ui.pathTracerComboBox.clear()
        self.gui.ui.pathTracerComboBox.addItems(self.renderer_options.path_tracers)

        alg_item = self.gui.ui.pathTracerComboBox.findText(self.renderer_options.algorithm_type)

        if alg_item >= 0:
            self.gui.ui.pathTracerComboBox.setCurrentIndex(alg_item)

        self.gui.ui.samplesPerPixelSpinBox.setValue(self.renderer_options.samples_per_pixel_count)

        self.gui.ui.pbrtPathLineEdit.setText(self.renderer_options.pbrt_path)

    def _setup_connections(self):
        self.gui.ui.buttonBox.rejected.connect(self.gui.window.close)
        self.gui.ui.buttonBox.accepted.connect(lambda: self.__change_renderer_options())
        self.gui.ui.pbrtPathButton.clicked.connect(self.__choose_pbrt_path)

    def __change_renderer_options(self):
        self.renderer_options.pixel_filter = u"{}".format(self.gui.ui.pixelFilterComboBox.itemText(self.gui.ui.pixelFilterComboBox.currentIndex()))
        self.renderer_options.samples_per_pixel_count = self.gui.ui.samplesPerPixelSpinBox.value()
        self.renderer_options.algorithm_type = u"{}".format(self.gui.ui.pathTracerComboBox.itemText(self.gui.ui.pathTracerComboBox.currentIndex()))
        self.renderer_options.pbrt_path = u"{}".format(self.gui.ui.pbrtPathLineEdit.text())
        self.new_task_dialog.set_renderer_options(self.renderer_options)
        self.gui.window.close()

    def __choose_pbrt_path(self):
        dir_ = os.path.dirname(u"{}".format(self.gui.ui.pbrtPathLineEdit.text()))
        file_name = u"{}".format(QFileDialog.getOpenFileName(self.gui.window, "Choose pbrt file", dir_, ""))
        if file_name != '':
            self.gui.ui.pbrtPathLineEdit.setText(file_name)
