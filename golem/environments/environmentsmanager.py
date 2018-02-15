import logging
import os
from configparser import ConfigParser, ParsingError
from importlib import import_module
from shutil import copy

from golem.core.common import get_golem_path
from golem.environments.environmentsconfig import EnvironmentsConfig
from .environment import Environment, SupportStatus, UnsupportReason

logger = logging.getLogger(__name__)

REGISTERED_ENVS_FILE = "registered_envs.ini"
REGISTERED_ENVS_TEST_FILE = "registered_envs_test.ini"


class EnvironmentsManager(object):
    """ Manage known environments. Allow user to choose accepted environment, keep track of supported environments """

    def __init__(self):
        self.support_statuses = {}
        self.environments = {}
        self.env_config = None

    def load_all_envs(self, datadir, mainnet):
        self._load_registered_envs(datadir, REGISTERED_ENVS_FILE)
        if not mainnet:
            self._load_registered_envs(datadir, REGISTERED_ENVS_TEST_FILE)

    def _load_registered_envs(self, datadir, config_filename):
        """
        Initializes registered environemnts. Looks for environments in
        datadir/config_filename. If this file does not exist, this method
        copies in new config_filename with default values.
        If datadir is None, just reads the default config in.
        """
        config_path = os.path.join(get_golem_path(), 'apps', config_filename)
        if datadir:
            local_config_path = os.path.join(datadir, config_filename)
            if not os.path.exists(local_config_path):
                copy(config_path, local_config_path)
            config_path = local_config_path

        try:
            parser = ConfigParser()
            parser.read_file(open(config_path))
            for task_type in parser.sections():
                envs = parser.get(task_type, 'envs').split(',')
                for env_cls in envs:
                    package, name = env_cls.rsplit('.', 1)
                    module = import_module(package)
                    env = getattr(module, name)
                    self.add_environment(task_type, env())
        except (ParsingError, ValueError):
            logger.error('Failed to parse config file %s', config_filename)
            # golem will not be working correctly without environments
            raise
        except (ModuleNotFoundError, AttributeError):
            logger.error(
                'Failed to import environments specified in config file %s',
                config_filename)
            raise

    def load_config(self, datadir):
        """ Load acceptance of environments from the config file
        :param datadir:
        """
        self.env_config = EnvironmentsConfig.load_config(
            self.get_environments_to_config(), datadir)
        config_entries = self.env_config.get_config_entries()
        for env in self.get_environments():
            getter_name = "get_" + env.get_id()
            if hasattr(config_entries, getter_name):
                getter_for_env = getattr(config_entries, getter_name)
                env.accept_tasks = getter_for_env()

    def add_environment(self, task_type: str, environment: Environment):
        """ Add new environment to the manager. Check if environment is supported.
        :param str task_type: task type for which this environment is added.
        :param Environment environment:
        """
        self._prepare_type_for_environment(task_type)
        self.environments[task_type].append(environment)
        supported = environment.check_support()
        logger.info("Adding environment %s for type %s; supported=%s",
                    environment.get_id(), task_type, supported)
        self.support_statuses[environment.get_id()] = supported

    def get_support_status(self, env_id) -> SupportStatus:
        """ Return information if given environment are supported.
            Uses information from supported environments,
            doesn't check the environment again.
        :param str env_id:
        :return SupportStatus:
        """
        return self.support_statuses.get(env_id, SupportStatus.err(
            {UnsupportReason.ENVIRONMENT_MISSING: env_id}))

    def accept_tasks(self, env_id):
        """Return information whether tasks from given environment are accepted.
        :param str env_id:
        :return bool:
        """
        for env in self.get_environments():
            if env.get_id() == env_id:
                return env.is_accepted()

    def get_environments(self):
        """ Return all known environments
        :return set:
        """
        return set().union(*self.environments.values())

    def get_environment_by_task_type(self, task_type):
        """ Return environment registered with given task_type
        :param task_type: type of task for which environment should be given
        :return: environment or None
        """
        env = None
        envs = self.environments.get(task_type, None)
        if envs:
            env = envs[0]
        return env

    def get_environment_by_id(self, env_id):
        for env in self.get_environments():
            if env.get_id() == env_id:
                return env
        return None

    def get_environments_to_config(self):
        envs = {}
        for env in self.get_environments():
            envs[env.get_id()] = (env.get_id(), True)
        return envs

    def change_accept_tasks(self, env_id, state):
        """ Change information whether tasks from this environment are accepted
            or not. Write changes in config file
        :param str env_id:
        :param bool state:
        """
        for env in self.get_environments():
            if env.get_id() == env_id:
                env.accept_tasks = state
                config_entries = self.env_config.get_config_entries()
                setter_for_env = getattr(config_entries, "set_" + env.get_id())
                setter_for_env(int(state))
                self.env_config = self.env_config.change_config()
                return

    def get_performance_values(self):
        perf_values = {env.get_id(): env.get_performance()
                       for env in self.get_environments()}
        if Environment.get_id() not in perf_values:
            perf_values[Environment.get_id()] = Environment.get_performance()
        return perf_values

    def get_benchmarks(self):
        """ Returns list of data representing benchmark for registered app
        :return dict: dictionary, where environment ids are the keys and values
        are defined as pairs of instance of Benchmark and class of task builder
        """
        return {env.get_id(): env.get_benchmark()
                for env in self.get_environments()}

    def _prepare_type_for_environment(self, task_type):
        if task_type not in self.environments:
            self.environments[task_type] = []
