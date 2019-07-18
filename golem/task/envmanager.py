import logging
from typing import Dict, List, NamedTuple, Type, Union

from golem.envs import EnvId, Environment
from golem.model import Performance
from golem.task.task_api import TaskApiPayloadBuilder
from twisted.internet.defer import Deferred

logger = logging.getLogger(__name__)


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
        if env_id not in self._state:
            return False
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

    def get_performance(self, env_id) -> Union[Deferred, float]:
        perf = None
        try:
            perf = Performance.get(Performance.environment_id == env_id)
        except Performance.DoesNotExist:
            pass

        if perf is None or perf.value is None:
            def _save_performance(raw_perf):
                Performance.update_or_create(env_id, raw_perf)

            def _benchmark_error(_e):
                logger.error('failed to run benchmark. env=%r', env_id)

            env = self._envs[env_id]
            deferred = env.run_benchmark()
            deferred.addCallback(_save_performance)
            deferred.addErrback(_benchmark_error)
            return deferred

        return perf.value
