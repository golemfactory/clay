import logging
import os
from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog
from copy import deepcopy

from verificationparamshelper import read_advance_verification_params, set_verification_widgets_state, \
    load_verification_params, verification_random_changed
from customizer import Customizer

logger = logging.getLogger(__name__)


class PbrtTaskDialogCustomizer(Customizer):
    def __init__(self, gui, logic, new_task_dialog):
        self.new_task_dialog = new_task_dialog
        self.options = deepcopy(new_task_dialog.options)
        Customizer.__init__(self, gui,logic)

    def load_data(self):
        self.__set_renderer_parameters()
        self.__set_output_parameters()
        self.__set_verification_parameters()

    def __set_renderer_parameters(self):
        self.gui.ui.pixelFilterComboBox.clear()
        self.gui.ui.pixelFilterComboBox.addItems(self.options.filters)
        pixel_filter_item = self.gui.ui.pixelFilterComboBox.findText(self.options.pixel_filter)
        if pixel_filter_item >= 0:
            self.gui.ui.pixelFilterComboBox.setCurrentIndex(pixel_filter_item)

        self.gui.ui.pathTracerComboBox.clear()
        self.gui.ui.pathTracerComboBox.addItems(self.options.path_tracers)

        alg_item = self.gui.ui.pathTracerComboBox.findText(self.options.algorithm_type)

        if alg_item >= 0:
            self.gui.ui.pathTracerComboBox.setCurrentIndex(alg_item)

        self.gui.ui.samplesPerPixelSpinBox.setValue(self.options.samples_per_pixel_count)
        # self.gui.ui.pbrtPathLineEdit.setText(self.options.pbrt_path)

        self.gui.ui.mainSceneLineEdit.setText(self.options.main_scene_file)

    def __set_output_parameters(self):
        self.gui.ui.outputResXSpinBox.setValue(self.options.resolution[0])
        self.gui.ui.outputResYSpinBox.setValue(self.options.resolution[1])

        self.gui.ui.outputFormatsComboBox.clear()
        self.gui.ui.outputFormatsComboBox.addItems(self.options.output_formats)
        for idx, output_format in enumerate(self.options.output_formats):
            if output_format == self.options.output_format:
                self.gui.ui.outputFormatsComboBox.setCurrentIndex(idx)

        self.gui.ui.outputFileLineEdit.setText(self.options.output_file)

    def __set_verification_parameters(self):
        load_verification_params(self.gui, self.options)

    def __set_verification_widgets_state(self, state):
        set_verification_widgets_state(self.gui, state)

    def _setup_connections(self):
        self.gui.ui.cancelButton.clicked.connect(self.gui.window.close)
        self.gui.ui.okButton.clicked.connect(lambda: self.__change_renderer_options())
        self.gui.ui.chooseOutputFileButton.clicked.connect(self.__choose_output_file_button_clicked)
        self.gui.ui.mainSceneButton.clicked.connect(self.__choose_main_scene_file_button_clicked)
        self.gui.ui.pbrtPathButton.clicked.connect(self.__choose_pbrt_path)
        QtCore.QObject.connect(self.gui.ui.outputResXSpinBox, QtCore.SIGNAL("valueChanged(const QString)"),
                               self.__res_x_changed)
        QtCore.QObject.connect(self.gui.ui.outputResYSpinBox, QtCore.SIGNAL("valueChanged(const QString)"),
                               self.__res_y_changed)
        QtCore.QObject.connect(self.gui.ui.verificationRandomRadioButton, QtCore.SIGNAL("toggled(bool)"),
                               self.__verification_random_changed)
        QtCore.QObject.connect(self.gui.ui.advanceVerificationCheckBox, QtCore.SIGNAL("stateChanged(int)"),
                               self.__advance_verification_changed)

    def __change_renderer_options(self):
        self.__read_renderer_params()
        self.__read_output_params()
        self.__read_verification_params()
        self.new_task_dialog.set_options(self.options)
        self.gui.window.close()

    def __read_renderer_params(self):
        self.options.pixel_filter = u"{}".format(
            self.gui.ui.pixelFilterComboBox.itemText(self.gui.ui.pixelFilterComboBox.currentIndex()))
        self.options.samples_per_pixel_count = self.gui.ui.samplesPerPixelSpinBox.value()
        self.options.algorithm_type = u"{}".format(
            self.gui.ui.pathTracerComboBox.itemText(self.gui.ui.pathTracerComboBox.currentIndex()))
        self.options.main_scene_file = os.path.normpath(u"{}".format(self.gui.ui.mainSceneLineEdit.text()))
        self.options.pbrt_path = u"{}".format(self.gui.ui.pbrtPathLineEdit.text())

    def __read_output_params(self):
        self.options.resolution = [self.gui.ui.outputResXSpinBox.value(), self.gui.ui.outputResYSpinBox.value()]
        self.options.output_file = u"{}".format(self.gui.ui.outputFileLineEdit.text())
        self.options.output_format = u"{}".format(
            self.gui.ui.outputFormatsComboBox.itemText(self.gui.ui.outputFormatsComboBox.currentIndex()))

    def __read_verification_params(self):
        return read_advance_verification_params(self.gui, self.options)

    def __choose_main_scene_file_button_clicked(self):
        output_file_types = " ".join([u"*.{}".format(ext) for ext in self.options.scene_file_ext])
        filter_ = u"Scene files ({})".format(output_file_types)

        dir_ = os.path.dirname(u"{}".format(self.gui.ui.mainSceneLineEdit.text()))

        file_name = u"{}".format(QFileDialog.getOpenFileName(self.gui.window,
                                                             "Choose main scene file", dir_, filter_))

        if file_name != '':
            self.gui.ui.mainSceneLineEdit.setText(file_name)

    def __choose_output_file_button_clicked(self):
        output_file_type = u"{}".format(self.gui.ui.outputFormatsComboBox.currentText())
        filter_ = u"{} (*.{})".format(output_file_type, output_file_type)

        dir_ = os.path.dirname(u"{}".format(self.gui.ui.outputFileLineEdit.text()))

        file_name = u"{}".format(QFileDialog.getSaveFileName(self.gui.window,
                                                             "Choose output file", dir_, filter_))

        if file_name != '':
            self.gui.ui.outputFileLineEdit.setText(file_name)

    def __choose_pbrt_path(self):
        dir_ = os.path.dirname(u"{}".format(self.gui.ui.pbrtPathLineEdit.text()))
        file_name = u"{}".format(QFileDialog.getOpenFileName(self.gui.window, "Choose pbrt file", dir_, ""))
        if file_name != '':
            self.gui.ui.pbrtPathLineEdit.setText(file_name)

    def __verification_random_changed(self):
        verification_random_changed(self.gui)

    def __res_x_changed(self):
        self.gui.ui.verificationSizeXSpinBox.setMaximum(self.gui.ui.outputResXSpinBox.value())

    def __res_y_changed(self):
        self.gui.ui.verificationSizeYSpinBox.setMaximum(self.gui.ui.outputResYSpinBox.value())

    def __advance_verification_changed(self):
        state = self.gui.ui.advanceVerificationCheckBox.isChecked()
        self.__set_verification_widgets_state(state)
