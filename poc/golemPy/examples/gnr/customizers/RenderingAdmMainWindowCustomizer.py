import logging

from examples.gnr.customizers.GNRAdministratorMainWindowCustomizer import GNRAdministratorMainWindowCustomizer
from examples.gnr.customizers.RenderingMainWindowCustomizer import AbsRenderingMainWindowCustomizer

logger = logging.getLogger(__name__)

##################################################################
class RenderingAdmMainWindowCustomizer(AbsRenderingMainWindowCustomizer, GNRAdministratorMainWindowCustomizer):
    def __init__(self, gui, logic):
        GNRAdministratorMainWindowCustomizer.__init__(self, gui, logic)
        self._setRenderingVariables()
        self._setupRenderingConnections()
        self._setupAdvanceTaskConnections()