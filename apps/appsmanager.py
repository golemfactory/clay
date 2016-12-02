from ConfigParser import ConfigParser
from os import path

from importlib import import_module

from golem.core.common import get_golem_path

REGISTERED_CONFIG_FILE = 'apps/registered.ini'


class AppsManager(object):
    """ Temporary solution for apps detection and management. """

    def __init__(self):
        self.apps = {}

    @classmethod
    def load_envs(cls):
        parser = ConfigParser()
        config_path = path.join(get_golem_path(), REGISTERED_CONFIG_FILE)
        parser.readfp(open(config_path))
        envs = []
        for section in parser.sections():
            full_env_name = parser.get(section, 'env')
            last_sep = full_env_name.rfind(".")
            env_name = full_env_name[last_sep+1:]
            env_mod_name = full_env_name[:last_sep]
            env_mod = import_module(env_mod_name)
            env = getattr(env_mod, env_name)
            envs.append(env())
        return envs






