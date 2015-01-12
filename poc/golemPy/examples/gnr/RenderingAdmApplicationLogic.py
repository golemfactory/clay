import logging

from examples.gnr.RenderingApplicationLogic import AbsRenderingApplicationLogic
from examples.gnr.GNRAdmApplicationLogic import GNRAdmApplicationLogic

logger = logging.getLogger(__name__)

##################################################################
class RenderingAdmApplicationLogic( AbsRenderingApplicationLogic, GNRAdmApplicationLogic ):
    def __init__( self ):
        GNRAdmApplicationLogic.__init__( self )
        AbsRenderingApplicationLogic.__init__( self )
