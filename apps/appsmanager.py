import os
from configparser import ConfigParser
from collections import OrderedDict
from importlib import import_module

from golem.config.active import APP_MANAGER_CONFIG_FILES
from golem.core.common import get_golem_path


class App(object):
    """ Basic Golem App Representation """
    def __init__(self):
        self.builder = None  # inherit from TaskBuilder
        self.task_type_info = None  # inherit from TaskTypeInfo


class AppsManager(object):
    """ Temporary solution for apps detection and management. """
    def __init__(self):
        self.apps = OrderedDict()

    def load_all_apps(self):
        for config_file in APP_MANAGER_CONFIG_FILES:
            self._load_apps(config_file)

    def _load_apps(self, apps_config_file):
        parser = ConfigParser()
        config_path = os.path.join(get_golem_path(), apps_config_file)

        with open(config_path) as config_file:
            parser.read_file(config_file)

        for section in parser.sections():
            app = App()
            for opt in vars(app):

                full_name = parser.get(section, opt)
                package, name = full_name.rsplit('.', 1)
                module = import_module(package)

                setattr(app, opt, getattr(module, name))

            self.apps[section] = app
