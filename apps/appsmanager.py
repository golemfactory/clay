import os
from configparser import ConfigParser
from collections import OrderedDict
from importlib import import_module
from typing import (
    Dict,
    List,
    TYPE_CHECKING,
    Tuple,
    Type,
)

from golem.config.active import APP_MANAGER_CONFIG_FILES
from golem.core.common import get_golem_path
from golem.environments.environment import SupportStatus

if TYPE_CHECKING:
    # pylint:disable=unused-import, ungrouped-imports
    from golem.environments.environment import Environment  # noqa: F401
    from golem.task.taskbase import TaskBuilder, TaskTypeInfo  # noqa: F401
    from apps.core.benchmark.benchmarkrunner import CoreBenchmark  # noqa: F401


class App(object):
    """ Basic Golem App Representation """
    def __init__(self):
        self.env: Type['Environment'] = None
        self.builder: Type['TaskBuilder'] = None
        self.task_type_info: Type['TaskTypeInfo'] = None
        self.benchmark: Type['CoreBenchmark'] = None
        self.benchmark_builder: Type['TaskBuilder'] = None


class AppsManager(object):
    """ Temporary solution for apps detection and management. """
    def __init__(self) -> None:
        self.apps: Dict[str, App] = OrderedDict()

    def load_all_apps(self) -> None:
        for config_file in APP_MANAGER_CONFIG_FILES:
            self._load_apps(config_file)

    def _load_apps(self, apps_config_file) -> None:

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

    def get_env_list(self) -> List['Environment']:
        return [app.env() for app in self.apps.values()]

    def get_benchmarks(self) \
            -> Dict[str, Tuple['CoreBenchmark', Type['TaskBuilder']]]:
        """ Returns list of data representing benchmark for registered app
        :return dict: dictionary, where environment ids are the keys and values
        are defined as pairs of instance of Benchmark and class of task builder
        """
        benchmarks = dict()

        for app in self.apps.values():
            env = app.env()
            if not self._benchmark_enabled(env):
                continue
            benchmarks[env.get_id()] = app.benchmark(), app.benchmark_builder

        return benchmarks

    @staticmethod
    def _benchmark_enabled(env) -> bool:
        return env.check_support() == SupportStatus.ok()
