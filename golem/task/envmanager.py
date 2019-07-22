import logging
from typing import Dict, List, NamedTuple, Type

from twisted.internet.defer import Deferred, inlineCallbacks

from golem.envs import EnvId, Environment
from golem.model import Performance
from golem.task.task_api import TaskApiPayloadBuilder

logger = logging.getLogger(__name__)


class EnvEntry(NamedTuple):
    instance: Environment
    payload_builder: Type[TaskApiPayloadBuilder]


class EnvironmentManager:
    """ Manager class for all Environments. """

    def __init__(self):
        self._envs: Dict[EnvId, EnvEntry] = {}
        self._state: Dict[EnvId, bool] = {}
        self._running_benchmark: bool = False

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
        """ Get the state (enabled or not) for an Environment.
            Also returns false when the environment is not registered"""
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

    @inlineCallbacks
    def get_performance(self, env_id) -> Deferred:
        """ Gets the performance for the given environment
            Checks the database first, if not found it starts a benchmark
            Return value Deferred resulting in a float
            or None when the benchmark is already running"""
        if self._running_benchmark:
            return None

        perf = None
        try:
            perf = Performance.get(Performance.environment_id == env_id)
            return perf.value
        except Performance.DoesNotExist:
            pass

        env = self._envs[env_id]
        self._running_benchmark = True

        try:
            result = yield env.run_benchmark()
        except Exception:
            logger.error('failed to run benchmark. env=%r', env_id)
            raise
        finally:
            self._running_benchmark = False

        Performance.update_or_create(env_id, result)
        logger.info(
            'Finshed running benchmark. env=%r, score=%r',
            env_id,
            result
        )
        return result
