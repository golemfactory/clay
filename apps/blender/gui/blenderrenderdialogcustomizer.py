import logging

from gui.customizers.renderercustomizer import FrameRendererCustomizer

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

    def _change_renderer_options(self):
        super(BlenderRenderDialogCustomizer, self)._change_renderer_options()
        self.renderer_options.compositing = self.gui.ui.compositingCheckBox.isChecked()

    def _setup_connections(self):
        super(BlenderRenderDialogCustomizer, self)._setup_connections()
        self._connect_with_task_settings_changed([self.gui.ui.compositingCheckBox.stateChanged])
