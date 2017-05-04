import logging

from apps.rendering.gui.controller.renderercustomizer import FrameRendererCustomizer

logger = logging.getLogger("apps.blender")


class BlenderRenderDialogCustomizer(FrameRendererCustomizer):
    """" Blender Render customizer class"""

    def get_task_name(self):
        return "Blender"

    def load_data(self):
        super(BlenderRenderDialogCustomizer, self).load_data()
        self._set_advanced_blender_options()

    def load_task_definition(self, definition):
        super(BlenderRenderDialogCustomizer, self).load_task_definition(definition)
        self._set_advanced_blender_options()

    def _set_advanced_blender_options(self):
        self.gui.ui.compositingCheckBox.setChecked(self.options.compositing)

    def _change_options(self):
        super(BlenderRenderDialogCustomizer, self)._change_options()
        self.options.compositing = self.gui.ui.compositingCheckBox.isChecked()