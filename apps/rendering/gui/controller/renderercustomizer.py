import logging
import os
from copy import deepcopy

from PyQt5.QtWidgets import QFileDialog

from apps.rendering.task.framerenderingtask import FrameRenderingTaskBuilder
from gui.controller.customizer import Customizer

logger = logging.getLogger("apps.rendering")


class RendererCustomizer(Customizer):
    def __init__(self, gui, logic):
        self.options = logic.options
        Customizer.__init__(self, gui, logic)

    def get_task_name(self):
        raise NotImplementedError

    def load_data(self):
        r = self.logic.get_task_type(self.get_task_name())

        self.gui.ui.outputResXSpinBox.setValue(
            r.defaults.resolution[0])
        self.gui.ui.outputResYSpinBox.setValue(
            r.defaults.resolution[1])

        # FIXME Move verification function to task specific widgets
        self.logic.customizer.gui.ui.verificationSizeXSpinBox.setMaximum(
            r.defaults.resolution[0])
        self.logic.customizer.gui.ui.verificationSizeYSpinBox.setMaximum(
            r.defaults.resolution[1])

        self.gui.ui.outputFormatsComboBox.clear()
        self.gui.ui.outputFormatsComboBox.addItems(r.output_formats)
        for i, output_format in enumerate(r.output_formats):
            if output_format == r.defaults.output_format:
                self.gui.ui.outputFormatsComboBox.setCurrentIndex(i)

        self.gui.ui.mainSceneFileLineEdit.clear()
        self.gui.ui.outputFileLineEdit.clear()
        self.options = self.logic.options

    def load_task_definition(self, definition):
        self.options = deepcopy(definition.options)
        self.gui.ui.mainSceneFileLineEdit.setText(definition.main_scene_file)
        self.gui.ui.outputResXSpinBox.setValue(definition.resolution[0])
        self.gui.ui.outputResYSpinBox.setValue(definition.resolution[1])
        self.gui.ui.outputFileLineEdit.setText(definition.output_file)

        output_format_item = self.gui.ui.outputFormatsComboBox.findText(definition.output_format)

        if output_format_item >= 0:
            self.gui.ui.outputFormatsComboBox.setCurrentIndex(output_format_item)
        else:
            logger.error("Cannot load task, wrong output format")
            return

        if os.path.normpath(definition.main_scene_file) in definition.resources:
            definition.resources.remove(os.path.normpath(definition.main_scene_file))

        self.save_setting('main_scene_path',
                          os.path.dirname(definition.main_scene_file))
        self.save_setting('output_file_path',
                          os.path.dirname(definition.output_file), sync=True)

    def get_task_specific_options(self, definition):
        self._change_options()
        definition.options = self.options
        definition.resolution = [self.gui.ui.outputResXSpinBox.value(), self.gui.ui.outputResYSpinBox.value()]
        definition.output_file = self._add_ext_to_out_filename()
        definition.output_format = u"{}".format(
            self.gui.ui.outputFormatsComboBox.itemText(self.gui.ui.outputFormatsComboBox.currentIndex()))
        definition.main_scene_file = u"{}".format(
            self.gui.ui.mainSceneFileLineEdit.text())

    def _change_options(self):
        pass

    def _setup_connections(self):
        self.gui.ui.chooseMainSceneFileButton.clicked.connect(
            self._choose_main_scene_file_button_clicked)
        self._setup_output_connections()
        self._connect_with_task_settings_changed([
            self.gui.ui.mainSceneFileLineEdit.textChanged,
        ])
        self.gui.ui.outputFormatsComboBox.currentIndexChanged.connect(self._add_ext_to_out_filename)
        self.gui.ui.outputFileLineEdit.editingFinished.connect(self._add_ext_to_out_filename)

    def _add_ext_to_out_filename(self):
        chosen_ext = str(self.gui.ui.outputFormatsComboBox.itemText(self.gui.ui.outputFormatsComboBox.currentIndex()))
        out_file_name = str(self.gui.ui.outputFileLineEdit.text())
        if not out_file_name:
            return ""
        file_name, ext = os.path.splitext(out_file_name)
        ext = ext[1:]
        if self.gui.ui.outputFormatsComboBox.findText(ext) != -1 or \
                        self.gui.ui.outputFormatsComboBox.findText(ext.upper()) != -1:
            self.gui.ui.outputFileLineEdit.setText(u"{}.{}".format(file_name, chosen_ext))
        else:
            self.gui.ui.outputFileLineEdit.setText(u"{}.{}".format(out_file_name, chosen_ext))
        return u"{}".format(str(self.gui.ui.outputFileLineEdit.text()))

    def _connect_with_task_settings_changed(self, list_gui_el):
        for gui_el in list_gui_el:
            gui_el.connect(self.logic.task_settings_changed)

    def _setup_output_connections(self):
        self.gui.ui.chooseOutputFileButton.clicked.connect(
            self._choose_output_file_button_clicked)
        self.gui.ui.outputResXSpinBox.valueChanged.connect(self._res_x_changed)
        self.gui.ui.outputResYSpinBox.valueChanged.connect(self._res_y_changed)

    def _choose_main_scene_file_button_clicked(self):
        tmp_output_file_ext = self.logic.get_current_task_type().output_file_ext
        output_file_ext = []
        for ext in tmp_output_file_ext:
            output_file_ext.append(ext.upper())
            output_file_ext.append(ext.lower())

        output_file_types = " ".join([u"*.{}".format(ext) for ext in output_file_ext])
        filter_ = u"Scene files ({})".format(output_file_types)
        path = u"{}".format(str(self.load_setting('main_scene_path', os.path.expanduser('~'))))

        file_name, _ = QFileDialog.getOpenFileName(self.gui,
                                                   "Choose main scene file",
                                                   path,
                                                   filter_)
        if file_name:
            self.save_setting('main_scene_path', os.path.dirname(file_name))
            self.gui.ui.mainSceneFileLineEdit.setText(file_name)

    def _choose_output_file_button_clicked(self):
        output_file_type = u"{}".format(self.gui.ui.outputFormatsComboBox.currentText())
        filter_ = u"{} (*.{})".format(output_file_type, output_file_type)

        path = u"{}".format(str(self.load_setting('output_file_path', os.path.expanduser('~'))))

        file_name, _ = QFileDialog.getSaveFileName(self.gui,
                                                   "Choose output file",
                                                   path,
                                                   filter_)
        if file_name:
            self.save_setting('output_file_path', os.path.dirname(file_name))
            self.gui.ui.outputFileLineEdit.setText(file_name)

    def _res_x_changed(self):
        self.logic.change_verification_option(size_x_max=self.gui.ui.outputResXSpinBox.value())

    def _res_y_changed(self):
        self.logic.change_verification_option(size_y_max=self.gui.ui.outputResYSpinBox.value())


class FrameRendererCustomizer(RendererCustomizer):
    def _setup_connections(self):
        super(FrameRendererCustomizer, self)._setup_connections()
        self.gui.ui.framesCheckBox.stateChanged.connect(self._frames_check_box_changed)
        self.gui.ui.framesLineEdit.textChanged.connect(self._frames_changed)
        self.gui.ui.framesCheckBox.stateChanged.connect(self._frames_changed)

    def load_data(self):
        super(FrameRendererCustomizer, self).load_data()
        self._set_frames_from_options()

    def load_task_definition(self, definition):
        super(FrameRendererCustomizer, self).load_task_definition(definition)
        self._set_frames_from_options()

    def _set_frames_from_options(self):
        self.gui.ui.framesCheckBox.setChecked(self.options.use_frames)
        self.gui.ui.framesLineEdit.setEnabled(self.options.use_frames)
        if self.options.use_frames:
            self.gui.ui.framesLineEdit.setText(self.options.frames)
        else:
            self.gui.ui.framesLineEdit.setText("")

    def _change_options(self):
        self.options.use_frames = self.gui.ui.framesCheckBox.isChecked()
        if self.options.use_frames:
            frames = self.gui.ui.framesLineEdit.text()
            # This is a temporary solution for current interface
            frames_list = FrameRenderingTaskBuilder.string_to_frames(frames)
            if not frames_list:
                self.show_error_window(u"Wrong frame format. "
                                       u"Frame list expected, e.g. 1;3;5-12.")
                return
        else:
            frames = "1"

        self.options.frames = frames
        # FIXME: CoreTask uses frames_string for frame conversion
        self.options.frames_string = frames

    def _frames_changed(self):
        self.logic.task_settings_changed()

    def _frames_check_box_changed(self):
        self.gui.ui.framesLineEdit.setEnabled(
            self.gui.ui.framesCheckBox.isChecked())
        if self.gui.ui.framesCheckBox.isChecked():
            self.gui.ui.framesLineEdit.setText(self.options.frames)
