from typing import Dict, List, NamedTuple, Type

from golem.envs import EnvId, Environment
from golem.task.appcallbacks.appcallbacks import TaskApiPayloadBuilder


class EnvEntry(NamedTuple):
    instance: Environment
    payload_builder: Type[TaskApiPayloadBuilder]


class EnvironmentManager:
    """ Manager class for all Environments. """

    def __init__(self):
        self._envs: Dict[EnvId, EnvEntry] = {}
        self._state: Dict[EnvId, bool] = {}

    def register_env(
            self,
            env: Environment,
            payload_builder: Type[TaskApiPayloadBuilder],
    ) -> None:
        """ Register an Environment (i.e. make it visible to manager). """
        env_id = env.metadata().id
        if env_id not in self._envs:
            self._envs[env_id] = EnvEntry(
                instance=env,
                payload_builder=payload_builder,
            )
            self._state[env_id] = False

    def state(self) -> Dict[EnvId, bool]:
        """ Get the state (enabled or not) for all registered Environments. """
        return dict(self._state)

    def set_state(self, state: Dict[EnvId, bool]) -> None:
        """ Set the state (enabled or not) for all registered Environments. """
        for env_id, enabled in state.items():
            self.set_enabled(env_id, enabled)

    def enabled(self, env_id: EnvId) -> bool:
        """ Get the state (enabled or not) for an Environment. """
        return self._state[env_id]

    def set_enabled(self, env_id: EnvId, enabled: bool) -> None:
        """ Set the state (enabled or not) for an Environment. This does *not*
            include actually activating or deactivating the Environment. """
        if env_id in self._state:
            self._state[env_id] = enabled

    def environments(self) -> List[Environment]:
        """ Get all registered Environments. """
        return [entry.instance for entry in self._envs.values()]

    def environment(self, env_id: EnvId) -> Environment:
        """ Get Environment with the given ID. Assumes such Environment is
            registered. """
        return self._envs[env_id].instance

    def payload_builder(self, env_id: EnvId) -> Type[TaskApiPayloadBuilder]:
        return self._envs[env_id].payload_builder
