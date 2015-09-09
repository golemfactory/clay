from golem.core.simpleenv import SimpleEnv
from golem.core.simpleconfig import SimpleConfig, ConfigEntry
import logging

ENV_VERSION = 1.01
CONFIG_FILENAME = "environments.ini"

logger = logging.getLogger(__name__)

############################################################
class CommonConfig:
    ##############################
    def __init__(self,
                 section = "Common",
                 envVersion = ENV_VERSION):

        self._section = section

        ConfigEntry.create_property(section, "environment version", envVersion, self, "envVersion")

    ##############################
    def section(self):
        return self._section

############################################################
class NodeConfig:
    ##############################
    def __init__(self, node_id, environments = []):
        self._section = "Node {}".format(node_id)

        for env_id, (envName, supported) in environments.iteritems():
            ConfigEntry.create_property(self.section(), env_id.lower(), int(supported), self, envName)

    ##############################
    def section(self):
        return self._section

############################################################
class EnvironmentsConfig:

    ##############################
    @classmethod
    def load_config(cls, node_id, environments, cfgFile = CONFIG_FILENAME):

        cfg  = SimpleConfig(CommonConfig(), NodeConfig(node_id, environments), cfgFile, refresh = False, check_uid = False)

        return EnvironmentsConfig(cfg)

    ##############################
    def __init__(self, cfg):
        self._cfg = cfg

    ##############################
    def get_config_entries(self):
        return self._cfg.get_node_config()

    ##############################
    def change_config(self, cfgFile = CONFIG_FILENAME):
        return EnvironmentsConfig(SimpleConfig(self._cfg.get_common_config(), self._cfg.get_node_config(), cfgFile,  refresh = True, check_uid = False))

    ##############################
    def __str__(self):
        return str(self._cfg)
