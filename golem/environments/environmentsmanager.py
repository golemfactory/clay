import logging
from typing import Dict, Optional, Tuple

from golem.environments.environmentsconfig import EnvironmentsConfig
from .environment import Environment, SupportStatus, UnsupportReason

logger = logging.getLogger(__name__)


class EnvironmentsManager(object):
    """ Manage known environments.

    Allow user to choose accepted environment,
    keep track of supported environments """

    def __init__(self) -> None:
        self.support_statuses: Dict[str, SupportStatus] = {}
        self.environments: Dict[str, Environment] = {}
        self.env_config: Optional[EnvironmentsConfig] = None

    def load_config(self, datadir: str) -> None:
        """ Load acceptance of environments from the config file
        """
        self.env_config = EnvironmentsConfig.load_config(
            self._get_environments_to_config(), datadir)
        config_entries = self.env_config.get_config_entries()
        for env_id, env in self.environments.items():
            getter_for_env = getattr(config_entries, "get_" + env_id)
            env.accept_tasks = bool(getter_for_env())

    def add_environment(self, environment: Environment) -> None:
        """ Add new environment to the manager. Check if environment is supported.
        """
        self.environments[environment.get_id()] = environment
        supported = environment.check_support()
        logger.info("Adding environment {} supported={}"
                    .format(environment.get_id(), supported))
        self.support_statuses[environment.get_id()] = supported

    def get_support_status(self, env_id: str) -> SupportStatus:
        """ Return information if given environment are supported.
            Uses information from supported environments,
            doesn't check the environment again.
        """
        return self.support_statuses.get(env_id, SupportStatus.err(
            {UnsupportReason.ENVIRONMENT_MISSING: env_id}))

    def accept_tasks(self, env_id: str) -> bool:
        """Return information whether tasks from given environment are accepted.
        """
        if env_id not in self.environments:
            return False
        return self.environments[env_id].is_accepted()

    def get_environments(self) -> Dict[str, Environment]:
        """ Return all known environments """
        return self.environments

    def get_environment_by_id(self, env_id: str) -> Optional[Environment]:
        return self.environments.get(env_id)

    def _get_environments_to_config(self) -> Dict[str, Tuple[str, bool]]:
        envs = {}
        for env_id in self.environments.keys():
            envs[env_id] = (env_id, True)
        return envs

    def change_accept_tasks(self, env_id: str, state: bool) -> None:
        """ Change information whether tasks from this environment are accepted
            or not. Write changes in config file
        """
        env = self.environments[env_id]
        env.accept_tasks = state
        config_entries = self.env_config.get_config_entries()
        setter_for_env = getattr(config_entries, "set_" + env.get_id())
        setter_for_env(int(state))
        self.env_config = self.env_config.change_config()

    def get_performance_values(self) -> Dict[str, float]:
        perf_values = {env_id: env.get_performance()
                       for env_id, env in self.environments.items()}
        if Environment.get_id() not in perf_values:
            perf_values[Environment.get_id()] = Environment.get_performance()
        return perf_values
