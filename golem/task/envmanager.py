import logging
from typing import Dict, List, Type, Optional

from dataclasses import dataclass
from twisted.internet.defer import Deferred, inlineCallbacks

from golem.envs import EnvId, Environment, EnvMetadata
from golem.model import Performance
from golem.task.task_api import TaskApiPayloadBuilder

logger = logging.getLogger(__name__)


class EnvironmentManager:
    """ Manager class for all Environments. """

    @dataclass
    class EnvEntry:
        instance: Environment
        metadata: EnvMetadata
        payload_builder: Type[TaskApiPayloadBuilder]

    def __init__(self):
        self._envs: Dict[EnvId, EnvironmentManager.EnvEntry] = {}
        self._state: Dict[EnvId, bool] = {}
        self._running_benchmark: bool = False

    def register_env(
            self,
            env: Environment,
            metadata: EnvMetadata,
            payload_builder: Type[TaskApiPayloadBuilder],
    ) -> None:
        """ Register an Environment (i.e. make it visible to manager). """
        if metadata.id in self._envs:
            raise ValueError(f"Environment '{metadata.id}' already registered.")
        self._envs[metadata.id] = EnvironmentManager.EnvEntry(
            instance=env,
            metadata=metadata,
            payload_builder=payload_builder,
        )
        self._state[metadata.id] = False

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

    def environments(self) -> List[EnvId]:
        """ Get all registered Environment IDs. """
        return [entry.metadata.id for entry in self._envs.values()]

    def environment(self, env_id: EnvId) -> Environment:
        """ Get Environment with the given ID. Assumes such Environment is
            registered. """
        return self._envs[env_id].instance

    def metadata(self, env_id: EnvId) -> EnvMetadata:
        """ Get metadata for environment with the given ID. """
        return self._envs[env_id].metadata

    def payload_builder(self, env_id: EnvId) -> Type[TaskApiPayloadBuilder]:
        """ Get payload builder class for environment with the given ID. """
        return self._envs[env_id].payload_builder

    @inlineCallbacks
    def get_performance(self, env_id) -> Deferred:
        """ Gets the performance for the given environment
            Checks the database first, if not found it starts a benchmark
            Return value Deferred resulting in a float
            or None when the benchmark is already running. """
        if self._running_benchmark:
            return None

        if not self.enabled(env_id):
            raise Exception("Requested performance for disabled environment")

        result = self.get_cached_performance(env_id)
        if result:
            return result

        env = self._envs[env_id].instance
        self._running_benchmark = True

        try:
            result = yield env.run_benchmark()
        except Exception:
            logger.error(
                'failed to run benchmark. env=%r',
                env_id,
                exc_info=True
            )
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

    @staticmethod
    def get_cached_performance(env_id: EnvId) -> Optional[float]:
        try:
            return Performance.get(Performance.environment_id == env_id).value
        except Performance.DoesNotExist:
            return None
