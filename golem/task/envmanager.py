import logging
from pathlib import Path
from typing import Dict, List, Type, Optional, TYPE_CHECKING

from dataclasses import dataclass
from peewee import PeeweeException
from twisted.internet.defer import inlineCallbacks, DeferredLock

from golem.envs import BenchmarkResult
from golem.envs.wrappers import auto_setup, dump_logs
from golem.model import Performance, EnvConfiguration

if TYPE_CHECKING:
    # pylint:disable=unused-import, ungrouped-imports
    from twisted.internet.defer import Deferred
    from golem.envs import EnvId, Environment, EnvMetadata
    from golem.task.task_api import TaskApiPayloadBuilder


logger = logging.getLogger(__name__)


class EnvironmentManager:
    """ Manager class for all Environments. Ensures that only one environment
        is used at a time. Lazily cleans up unused environments."""

    @dataclass
    class EnvEntry:
        instance: 'Environment'
        metadata: 'EnvMetadata'
        payload_builder: 'Type[TaskApiPayloadBuilder]'

    def __init__(self, runtime_logs_dir: Path) -> None:
        self._runtime_logs_dir = runtime_logs_dir
        self._envs: 'Dict[EnvId, EnvironmentManager.EnvEntry]' = {}
        self._state = EnvStates()
        self._running_benchmark: bool = False
        self._lock = DeferredLock()
        self._active_env: 'Optional[Environment]' = None

    @inlineCallbacks
    def _start_usage(self, env: 'Environment') -> 'Deferred':
        yield self._lock.acquire()

        if self._active_env is env:
            return

        if self._active_env is not None:
            try:
                yield self._active_env.clean_up()
                self._active_env = None
            except Exception:
                yield self._lock.release()
                raise

        try:
            yield env.prepare()
            self._active_env = env
        except Exception:
            yield self._lock.release()
            raise

    @inlineCallbacks
    def _end_usage(self, env: 'Environment') -> 'Deferred':
        if self._active_env is not env:
            raise ValueError('end_usage called for wrong environment')
        yield self._lock.release()

    def register_env(
            self,
            env: 'Environment',
            metadata: 'EnvMetadata',
            payload_builder: 'Type[TaskApiPayloadBuilder]',
    ) -> None:
        """ Register an Environment (i.e. make it visible to manager). """
        if metadata.id in self._envs:
            raise ValueError(f"Environment '{metadata.id}' already registered.")

        # Apply automatic setup wrapper
        wrapped_env = auto_setup.auto_setup(
            env=env,
            start_usage=self._start_usage,
            end_usage=self._end_usage
        )

        # Apply runtime logs wrapper
        logs_dir = self._runtime_logs_dir / metadata.id
        logs_dir.mkdir(parents=True, exist_ok=True)
        wrapped_env = dump_logs.dump_logs(
            env=wrapped_env,
            logs_dir=logs_dir
        )

        self._envs[metadata.id] = EnvironmentManager.EnvEntry(
            instance=wrapped_env,
            metadata=metadata,
            payload_builder=payload_builder,
        )
        if metadata.id not in self._state:
            self._state[metadata.id] = False

    def state(self) -> 'Dict[EnvId, bool]':
        """ Get the state (enabled or not) for all registered Environments. """
        return self._state.copy()

    def set_state(self, state: 'Dict[EnvId, bool]') -> None:
        """ Set the state (enabled or not) for all registered Environments. """
        for env_id, enabled in state.items():
            self.set_enabled(env_id, enabled)

    def enabled(self, env_id: 'EnvId') -> bool:
        """ Get the state (enabled or not) for an Environment.
            Also returns false when the environment is not registered"""
        if env_id not in self._envs or env_id not in self._state:
            return False
        return self._state[env_id]

    def set_enabled(self, env_id: 'EnvId', enabled: bool) -> None:
        """ Set the state (enabled or not) for an Environment. This does *not*
            include actually activating or deactivating the Environment. """
        if env_id in self._state:
            self._state[env_id] = enabled

    def environments(self) -> 'List[EnvId]':
        """ Get all registered Environment IDs. """
        return [entry.metadata.id for entry in self._envs.values()]

    def environment(self, env_id: 'EnvId') -> 'Environment':
        """ Get Environment with the given ID. Assumes such Environment is
            registered. """
        return self._envs[env_id].instance

    def metadata(self, env_id: 'EnvId') -> 'EnvMetadata':
        """ Get metadata for environment with the given ID. """
        return self._envs[env_id].metadata

    def payload_builder(self, env_id: 'EnvId') -> Type['TaskApiPayloadBuilder']:
        """ Get payload builder class for environment with the given ID. """
        return self._envs[env_id].payload_builder

    @inlineCallbacks
    def get_benchmark_result(self, env_id) -> 'Deferred':
        """ Gets the performance for the given environment
            Checks the database first, if not found it starts a benchmark
            :return Deferred resulting in a BenchmarkResult object or None
            when the benchmark is already running. """
        if self._running_benchmark:
            return None

        if not self.enabled(env_id):
            raise Exception("Requested performance for disabled environment")

        result = self.get_cached_benchmark_result(env_id)
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

        Performance.update_or_create(
            env_id=env_id,
            performance=result.performance,
            cpu_usage=result.cpu_usage
        )

        logger.info(
            'Finished running benchmark. env=%r, score=%r, cpu_usage=%r',
            env_id,
            result.performance,
            result.cpu_usage
        )

        return result

    @staticmethod
    def get_cached_benchmark_result(env_id: 'EnvId'):
        try:
            perf = Performance.get(Performance.environment_id == env_id)
            return BenchmarkResult.from_performance(perf)
        except Performance.DoesNotExist:
            return None

    @staticmethod
    def remove_cached_performance(env_id: 'EnvId') -> None:
        try:
            query = Performance.delete().where(
                Performance.environment_id == env_id)
            query.execute()
        except PeeweeException:
            logger.exception(f"Cannot clear performance score for '{env_id}'")


class EnvStates:

    @staticmethod
    def copy() -> Dict['EnvId', bool]:
        configs = EnvConfiguration.select().execute()
        return {config.env_id: config.enabled for config in configs}

    def __contains__(self, item):
        if not isinstance(item, str):
            self._raise_no_str_type(item)

        return EnvConfiguration.select(EnvConfiguration.env_id) \
            .where(EnvConfiguration.env_id == item) \
            .exists()

    def __getitem__(self, item):
        if not isinstance(item, str):
            self._raise_no_str_type(item)
        try:
            return EnvConfiguration \
                .get(EnvConfiguration.env_id == item) \
                .enabled
        except EnvConfiguration.DoesNotExist:
            raise KeyError(item)

    def __setitem__(self, key, val):
        if not isinstance(key, str):
            self._raise_no_str_type(key)
        if not isinstance(val, bool):
            raise TypeError(f"Value is of type {type(val)}; bool expected")

        EnvConfiguration.insert(env_id=key, enabled=val).upsert().execute()

    @staticmethod
    def _raise_no_str_type(item):
        raise TypeError(f"Key is of type {type(item)}; str expected")
