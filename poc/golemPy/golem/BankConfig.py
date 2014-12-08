from golem.core.simpleenv import SimpleEnv
from golem.core.simpleconfig import SimpleConfig, ConfigEntry
import logging

START_BUDGET = 42000000
PRICE_BASE = 10
CONFIG_FILENAME = "bank.ini"

logger = logging.getLogger(__name__)

############################################################
class CommonConfig:
    ##############################
    def __init__(self,
                 section = "Common",
                 priceBase = PRICE_BASE):

        self._section = section

        ConfigEntry.createProperty( section, "price base", priceBase, self, "PriceBase" )

    ##############################
    def section( self ):
        return self._section

############################################################
class NodeConfig:
    ##############################
    def __init__( self, nodeId, budget = START_BUDGET ):
        self._section = "Node {}".format( nodeId )

        ConfigEntry.createProperty( self.section(), "budget", budget, self, "Budget" )
        ConfigEntry.createProperty( self.section(), "bank client UUID",         u"",   self, "ClientUid" )

    ##############################
    def section( self ):
        return self._section

############################################################
class BankConfig:

    ##############################
    @classmethod
    def loadConfig( cls, nodeId, cfgFile = CONFIG_FILENAME ):

        logger = logging.getLogger(__name__)

        cfg  = SimpleConfig( CommonConfig(), NodeConfig( nodeId ), cfgFile )

        return BankConfig( cfg )

    ##############################
    def __init__( self, cfg ):
        self._cfg = cfg

    ##############################
    def getPriceBase( self ):
        return self._cfg.getCommonConfig().getPriceBase()

    ##############################
    def getBudget( self ):
        return self._cfg.getNodeConfig().getBudget()

    ##############################
    def addToBudget( self, amount, cfgFile = CONFIG_FILENAME ):
        budget = self._cfg.getNodeConfig().getBudget()
        budget += amount
        self._cfg.getNodeConfig().setBudget( budget )
        SimpleConfig( self._cfg.getCommonConfig(), self._cfg.getNodeConfig(), cfgFile, True )

    ##############################
        def __str__( self ):
            return str( self._cfg )
