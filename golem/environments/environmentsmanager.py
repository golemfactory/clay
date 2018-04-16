import logging
import os
import re
from configparser import ConfigParser, ParsingError
from importlib import import_module
from shutil import copy
from typing import Dict, List, Optional

from golem.core.common import get_golem_path
from golem.environments.environmentsconfig import EnvironmentsConfig
from .environment import Environment

logger = logging.getLogger(__name__)

REGISTERED_ENVS_FILE = "registered_envs.ini"
REGISTERED_ENVS_TEST_FILE = "registered_envs_test.ini"


class EnvironmentsManager(object):
    """ Manage known environments. Allow user to choose accepted environment,
    keep track of supported environments """

    def __init__(self):
        self.environments_for_tasks: Dict[str, List[Environment]] = {}
        self.env_config = None

    def load_all_envs(self, datadir, mainnet):
        self._load_registered_envs(datadir, REGISTERED_ENVS_FILE)
        if not mainnet:
            self._load_registered_envs(datadir, REGISTERED_ENVS_TEST_FILE)

    # pylint: disable=too-many-locals
    def _load_registered_envs(self, datadir, config_filename):
        """
        Initializes registered environemnts. Looks for environments in
        datadir/config_filename. If this file does not exist, this method
        copies in new config_filename with default values.
        If datadir is None, just reads the default config in.
        """
        def parse_args(args: str) -> Dict[str, str]:
            argslist = (arg.split('=') for arg in args.split(',')
                        if re.match(r'\w+=\w+', arg))
            return {arg[0]: arg[1] for arg in argslist}

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
                envs = parser.get(task_type, 'envs').split(';')
                for env_entry in envs:
                    # each env entry is formed
                    # pa.ck.age.cls_name(opt1=val1,opt2=val2...)
                    m = re.match(r'([a-zA-Z.]+)\((.*)\)', env_entry.strip())
                    if not m:
                        raise ValueError(
                            f'In config file {config_path}:'
                            f' entry {env_entry} cannot be parsed.')
                    env_cls, args = m.groups()

                    package, name = env_cls.rsplit('.', 1)
                    module = import_module(package)
                    env = getattr(module, name)

                    kwargs = parse_args(args)
                    self.add_environment(task_type, env.create(**kwargs))
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
        """ Add new environment to the manager. Check if environment
        is supported.
        :param str task_type: task type for which this environment is added.
        :param Environment environment:
        """
        self._prepare_type_for_environment(task_type)
        self.environments_for_tasks[task_type].append(environment)
        supported = environment.check_support()
        logger.info("Adding environment %s for type %s; supported=%s",
                    environment.get_id(), task_type, supported)

    def get_environments(self):
        """ Return all known environments
        :return set:
        """
        return set().union(*self.environments_for_tasks.values())

    def get_environment_for_task(self, task_type, requirements) \
            -> Optional[Environment]:
        """ Return environment suitable for given task_type and requirements.
        Takes into account environments 'accept_tasks' and support
        status, returns first Environment for given task_type that is enabled
        and satisfies all the requirements
        :param task_type: type of task
        :param requirements: list of requirements which must be satisfied
        :return: environment or None
        """
        envs = (e for e in self.environments_for_tasks.get(task_type, [])
                if e.check_support()
                and e.is_accepted()
                and e.satisfies_requirements(requirements))
        return next(envs, None)

    def get_environment_by_id(self, env_id):
        for env in self.get_environments():
            if env.get_id() == env_id:
                return env
        return None

    def get_environments_to_config(self):
        return [(env.get_id(), True) for env in self.get_environments()]

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
        if Environment.DEFAULT_ID not in perf_values:
            perf_values[Environment.DEFAULT_ID] = \
                Environment.get_performance_for_id(Environment.DEFAULT_ID)
        return perf_values

    def get_benchmarks(self):
        """ Returns list of data representing benchmark for registered app
        :return dict: dictionary, where environment ids are the keys and values
        are defined as pairs of instance of Benchmark and class of task builder
        """
        return {env.get_id(): env.get_benchmark()
                for env in self.get_environments()}

    def _prepare_type_for_environment(self, task_type):
        if task_type not in self.environments_for_tasks:
            self.environments_for_tasks[task_type] = []
