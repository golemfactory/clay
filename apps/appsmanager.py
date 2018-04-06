import os
from configparser import ConfigParser
from collections import OrderedDict
from importlib import import_module

from golem.core.common import get_golem_path

REGISTERED_CONFIG_FILE = os.path.join('apps', 'registered.ini')
REGISTERED_TEST_CONFIG_FILE = os.path.join('apps', 'registered_test.ini')

class App(object):
    """ Basic Golem App Representation """
    def __init__(self):
        self.env = None  # inherit from Environment
        self.builder = None  # inherit from TaskBuilder
        self.task_type_info = None  # inherit from TaskTypeInfo
        self.benchmark = None  # inherit from Benchmark
        self.benchmark_builder = None #inherit from TaskBuilder


class AppsManager(object):
    """ Temporary solution for apps detection and management. """
    def __init__(self, mainnet):
        self.apps = OrderedDict()
        self._mainnet = mainnet

    def load_all_apps(self):
        self._load_apps(REGISTERED_CONFIG_FILE)
        if not self._mainnet:
            self._load_apps(REGISTERED_TEST_CONFIG_FILE)

    def _load_apps(self, apps_config_file):

        parser = ConfigParser()
        config_path = os.path.join(get_golem_path(), apps_config_file)
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

    def get_benchmarks(self):
        """ Returns list of data representing benchmark for registered app
        :return dict: dictionary, where environment ids are the keys and values
        are defined as pairs of instance of Benchmark and class of task builder
        """
        return {app.env().get_id(): (app.benchmark(), app.benchmark_builder)
                for app in self.apps.values()}
