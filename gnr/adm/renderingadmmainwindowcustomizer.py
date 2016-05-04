import logging

from gnr.customizers.gnradministratormainwindowcustomizer import GNRAdministratorMainWindowCustomizer
from gnr.customizers.renderingmainwindowcustomizer import AbsRenderingMainWindowCustomizer

logger = logging.getLogger(__name__)


class RenderingAdmMainWindowCustomizer(AbsRenderingMainWindowCustomizer, GNRAdministratorMainWindowCustomizer):
    def __init__(self, gui, logic):
        GNRAdministratorMainWindowCustomizer.__init__(self, gui, logic)
        self._set_rendering_variables()
        self._setup_rendering_connections()
        self._setup_advance_task_connections()