from __future__ import absolute_import

import os
from ConfigParser import ConfigParser
from collections import OrderedDict
from importlib import import_module

from golem.core.common import get_golem_path

REGISTERED_CONFIG_FILE = os.path.join('apps', 'registered.ini')


class App(object):
    """ Basic Golem App Representation """
    def __init__(self):
        self.env = None  # inherit from Environment
        self.builder = None  # inherit from TaskBuilder
        self.widget = None  # inherit from TaskWidget
        self.controller = None  # inherit from Customizer
        self.task_type_info = None  # inherit from TaskTypeInfo


class AppsManager(object):
    """ Temporary solution for apps detection and management. """
    def __init__(self):
        self.apps = OrderedDict()

    def load_apps(self):

        parser = ConfigParser()
        config_path = os.path.join(get_golem_path(), REGISTERED_CONFIG_FILE)
        parser.readfp(open(config_path))

        for section in parser.sections():
            app = App()
            for opt in vars(app):

                full_name = parser.get(section, opt)
                package, name = full_name.rsplit('.', 1)
                module = import_module(package)

                setattr(app, opt, getattr(module, name))

            self.apps[section] = app

    def get_env_list(self):
        return [app.env() for app in self.apps.values()]
