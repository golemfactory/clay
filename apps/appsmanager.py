import os
from collections import OrderedDict
from ConfigParser import ConfigParser
from os import path

from importlib import import_module

from golem.core.common import get_golem_path

REGISTERED_CONFIG_FILE = os.path.join('apps', 'registered.ini')


class App(object):
    def __init__(self):
        self.env = None
        self.builder = None
        self.widget = None
        self.controller = None
        self.build_info = None


class AppsManager(object):
    """ Temporary solution for apps detection and management. """
    def __init__(self):
        self.apps = OrderedDict()

    def load_apps(self):
        parser = ConfigParser()
        config_path = path.join(get_golem_path(), REGISTERED_CONFIG_FILE)
        parser.readfp(open(config_path))
        envs = []
        for section in parser.sections():
            app = App()
            for opt in vars(app):
                full_name = parser.get(section, opt)
                last_sep = full_name.rfind(".")
                name = full_name[last_sep+1:]
                mod_name = full_name[:last_sep]
                el_mod = import_module(mod_name)
                el = getattr(el_mod, name)
                setattr(app, opt, el)
            self.apps[section] = app

    def get_env_list(self):
        return [app.env() for app in self.apps.values()]







