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
        self.gui.ui.manualZerosCheckBox.setChecked(self.renderer_options.set_leading_zeros)
        if self.renderer_options.set_leading_zeros:
            self.gui.ui.leadingZerosSpinBox.setValue(int(self.renderer_options.leading_zeros))

    def _change_renderer_options(self):
        super(BlenderRenderDialogCustomizer, self)._change_renderer_options()
        self.renderer_options.compositing = self.gui.ui.compositingCheckBox.isChecked()
        if self.gui.ui.manualZerosCheckBox.isChecked():
            self.renderer_options.leading_zeros = self.gui.ui.leadingZerosSpinBox.value()
        else:
            self.renderer_options.leading_zeros = 0
        self.renderer_options.set_leading_zeros = self.gui.ui.manualZerosCheckBox.isChecked()

    def _setup_connections(self):
        super(BlenderRenderDialogCustomizer, self)._setup_connections()
        self._connect_with_task_settings_changed([self.gui.ui.compositingCheckBox.stateChanged,
                                                  self.gui.ui.manualZerosCheckBox.stateChanged,
                                                  self.gui.ui.leadingZerosSpinBox.valueChanged])
        self.gui.ui.manualZerosCheckBox.stateChanged.connect(self._set_enabled)

    def _set_enabled(self):
        self.gui.ui.leadingZerosSpinBox.setEnabled(self.gui.ui.manualZerosCheckBox.isChecked())
