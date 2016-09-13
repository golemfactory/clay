import logging

from renderercustomizer import FrameRendererCustomizer

logger = logging.getLogger("gnr.gui")


class BlenderRenderDialogCustomizer(FrameRendererCustomizer):
    """" Blender Render customizer class"""

    def get_task_name(self):
        return "Blender"

    def load_data(self):
        super(BlenderRenderDialogCustomizer, self).load_data()
        self._set_advance_blender_options()

    def load_task_definition(self, definition):
        super(BlenderRenderDialogCustomizer, self).load_task_definition(definition)
        self._set_advance_blender_options()

    def _set_advance_blender_options(self):
        self.gui.ui.compositingCheckBox.setChecked(self.renderer_options.compositing)
        self.gui.ui.paddingCheckBox.setChecked(self.renderer_options.use_padding)
        if self.renderer_options.use_padding:
            self.gui.ui.paddingSpinBox.setValue(int(self.renderer_options.pad_to_length))

    def _change_renderer_options(self):
        super(BlenderRenderDialogCustomizer, self)._change_renderer_options()
        self.renderer_options.compositing = self.gui.ui.compositingCheckBox.isChecked()
        if self.gui.ui.paddingCheckBox.isChecked():
            self.renderer_options.pad_to_length = self.gui.ui.paddingSpinBox.value()
        else:
            self.renderer_options.pad_to_length = 0
        self.renderer_options.use_padding = self.gui.ui.paddingCheckBox.isChecked()

    def _setup_connections(self):
        super(BlenderRenderDialogCustomizer, self)._setup_connections()
        self._connect_with_task_settings_changed([self.gui.ui.compositingCheckBox.stateChanged,
                                                  self.gui.ui.paddingCheckBox.stateChanged,
                                                  self.gui.ui.paddingSpinBox.valueChanged])
        self.gui.ui.paddingCheckBox.stateChanged.connect(self._set_enabled)

    def _set_enabled(self):
        self.gui.ui.paddingSpinBox.setEnabled(self.gui.ui.paddingCheckBox.isChecked())
