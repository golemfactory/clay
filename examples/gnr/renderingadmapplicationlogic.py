import logging

from examples.gnr.renderingapplicationlogic import AbsRenderingApplicationLogic
from examples.gnr.gnradmapplicationlogic import GNRAdmApplicationLogic

logger = logging.getLogger(__name__)


class RenderingAdmApplicationLogic(AbsRenderingApplicationLogic, GNRAdmApplicationLogic):
    def __init__(self):
        GNRAdmApplicationLogic.__init__(self)
        AbsRenderingApplicationLogic.__init__(self)
