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
    def __init__(self, environments):
        self._section = "Node"

        for env_id, (env_name, supported) in environments.iteritems():
            ConfigEntry.create_property(self.section(), env_id.lower(), int(supported), self, env_name)

    def section(self):
        return self._section


class EnvironmentsConfig(object):
    """Manage config file describing whether user want to compute tasks from given environment or not."""
    @classmethod
    def load_config(cls, environments, datadir):
        cfg_file = path.join(datadir, CONFIG_FILENAME)
        cfg = SimpleConfig(NodeConfig(environments),
                           cfg_file, refresh=False)

        return EnvironmentsConfig(cfg, cfg_file)

    def __init__(self, cfg, cfg_file):
        self._cfg = cfg
        self.cfg_file = cfg_file

    def get_config_entries(self):
        return self._cfg.get_node_config()

    def change_config(self):
        return EnvironmentsConfig(
            SimpleConfig(self._cfg.get_node_config(),
                         self.cfg_file, refresh=True),
            self.cfg_file
        )
