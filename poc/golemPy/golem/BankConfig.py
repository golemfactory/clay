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
                 price_base = PRICE_BASE):

        self._section = section

        ConfigEntry.create_property(section, "price base", price_base, self, "PriceBase")

    ##############################
    def section(self):
        return self._section

############################################################
class NodeConfig:
    ##############################
    def __init__(self, node_id, budget = START_BUDGET):
        self._section = "Node {}".format(node_id)

        ConfigEntry.create_property(self.section(), "budget", budget, self, "Budget")

    ##############################
    def section(self):
        return self._section

############################################################
class BankConfig:

    ##############################
    @classmethod
    def loadConfig(cls, node_id, cfgFile = CONFIG_FILENAME):

        logger = logging.getLogger(__name__)

        cfg  = SimpleConfig(CommonConfig(), NodeConfig(node_id), cfgFile, True, False)

        return BankConfig(cfg)

    ##############################
    def __init__(self, cfg):
        self._cfg = cfg

    ##############################
    def getPriceBase(self):
        return self._cfg.get_common_config().getPriceBase()

    ##############################
    def getBudget(self):
        return self._cfg.get_node_config().getBudget()

    ##############################
    def addToBudget(self, amount, cfgFile = CONFIG_FILENAME):
        budget = self._cfg.get_node_config().getBudget()
        budget += amount
        self._cfg.get_node_config().setBudget(budget)
        SimpleConfig(self._cfg.get_common_config(), self._cfg.get_node_config(), cfgFile, True, False)

    ##############################
        def __str__(self):
            return str(self._cfg)
