import logging

from renderercustomizer import FrameRendererCustomizer

logger = logging.getLogger(__name__)


class BlenderRenderDialogCustomizer(FrameRendererCustomizer):
    """" Blender Render customizer class"""

    def get_task_name(self):
        return "Blender"



