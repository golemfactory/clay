from golem.core.simpleconfig import SimpleConfig, ConfigEntry
import logging
from os import path

ENV_VERSION = 1.01
CONFIG_FILENAME = "environments.ini"

logger = logging.getLogger(__name__)


class CommonConfig(object):
    def __init__(self,
                 section="Common",
                 env_version=ENV_VERSION):
        self._section = section

        ConfigEntry.create_property(section, "environment version", env_version, self, "env_version")

    def section(self):
        return self._section


class NodeConfig(object):
    def __init__(self, node_name, environments):
        self._section = "Node {}".format(node_name)

        for env_id, (env_name, supported) in environments.iteritems():
            ConfigEntry.create_property(self.section(), env_id.lower(), int(supported), self, env_name)

    def section(self):
        return self._section


class EnvironmentsConfig(object):
    """Manage config file describing whether user want to compute tasks from given environment or not."""
    @classmethod
    def load_config(cls, node_name, environments, datadir):
        cfg_file = path.join(datadir, CONFIG_FILENAME)
        cfg = SimpleConfig(CommonConfig(), NodeConfig(node_name, environments),
                           cfg_file, refresh=False, check_uid=False)

        return EnvironmentsConfig(cfg)

    def __init__(self, cfg):
        self._cfg = cfg

    def get_config_entries(self):
        return self._cfg.get_node_config()

    def change_config(self, cfg_file=CONFIG_FILENAME):
        return EnvironmentsConfig(
            SimpleConfig(self._cfg.get_common_config(), self._cfg.get_node_config(), cfg_file, refresh=True,
                         check_uid=False))

    def __str__(self):
        return str(self._cfg)
