import logging
from golem.environments.environmentsconfig import EnvironmentsConfig

logger = logging.getLogger(__name__)


class EnvironmentsManager(object):
    """ Manage known environments. Allow user to choose accepted environment, keep track of supported environments """
    def __init__(self):
        self.supported_environments = set()
        self.environments = set()
        self.env_config = None

    def load_config(self, datadir):
        """ Load acceptance of environments from the config file
        :param datadir:
        """
        self.env_config = EnvironmentsConfig.load_config(self.get_environments_to_config(), datadir)
        config_entries = self.env_config.get_config_entries()
        for env in self.environments:
            getter_for_env = getattr(config_entries, "get_" + env.get_id())
            env.accept_tasks = getter_for_env()

    def add_environment(self, environment):
        """ Add new environment to the manager. Check if environment is supported.
        :param Environment environment:
        """
        self.environments.add(environment)
        supported = environment.supported()
        logger.info("Adding environment {} supported={}"
                    .format(environment.get_id(), supported))
        if supported:
            self.supported_environments.add(environment.get_id())

    def supported(self, env_id):
        """ Return information if given environment are supported. Uses information from supported environments, doesn't
         check the environment again.
        :param str env_id:
        :return bool:
        """
        return env_id in self.supported_environments

    def accept_tasks(self, env_id):
        """ Return information whether tasks from given environment are accepted.
        :param str env_id:
        :return bool:
        """
        for env in self.environments:
            if env.get_id() == env_id:
                return env.is_accepted()

    def get_environments(self):
        """ Return all known environments
        :return set:
        """
        return self.environments
    
    def get_environment_by_id(self, env_id):
        for env in self.environments:
            if env.get_id() == env_id:
                return env
        return None

    def get_environments_to_config(self):
        envs = {}
        for env in self.environments:
            envs[env.get_id()] = (env.get_id(), True)
        return envs

    def change_accept_tasks(self, env_id, state):
        """ Change information whether tasks from this environment are accepted or not. Write changes in config file
        :param str env_id:
        :param bool state:
        """
        for env in self.environments:
            if env.get_id() == env_id:
                env.accept_tasks = state
                config_entries = self.env_config.get_config_entries()
                setter_for_env = getattr(config_entries, "set_" + env.get_id())
                setter_for_env(int(state))
                self.env_config = self.env_config.change_config()
                return
