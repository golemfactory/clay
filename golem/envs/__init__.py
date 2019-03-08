from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from twisted.internet.defer import Deferred

CounterId = str
CounterUsage = Any

EnvId = str
EnvSupportStatus = bool
EnvConfig = Dict[str, Any]

EnvEventId = str
EnvEvent = Any  # TODO: Define environment events

RuntimeEventId = str
RuntimeEvent = Any  # TODO: Define runtime events


class Payload:
    pass


class RuntimeStatus(Enum):
    CREATED = 0
    PREPARING = 1
    PREPARED = 2
    STARTING = 3
    STARTED = 4
    RUNNING = 5
    STOPPED = 6
    CLEANING_UP = 7
    TORN_DOWN = 8
    FAILURE = 9


class Runtime(ABC):

    @abstractmethod
    def start(self) -> Deferred:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> Deferred:
        raise NotImplementedError

    @abstractmethod
    def status(self) -> RuntimeStatus:
        raise NotImplementedError

    @abstractmethod
    def usage_counters(self) -> Dict[CounterId, CounterUsage]:
        raise NotImplementedError

    @abstractmethod
    def listen(self, event_id: RuntimeEventId,
               callback: Callable[[RuntimeEvent], Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def call(self, alias: str, *args, **kwargs) -> Deferred:
        raise NotImplementedError


class EnvMetadata:
    id: EnvId
    description: str
    supported_counters: List[CounterId]
    custom_metadata: Dict[str, Any]


class EnvStatus(Enum):
    DISABLED = 0
    PREPARING = 1
    ENABLED = 2
    CLEANING_UP = 3


class Environment(ABC):

    @classmethod
    @abstractmethod
    def supported(cls) -> EnvSupportStatus:
        raise NotImplementedError

    @abstractmethod
    def status(self) -> EnvStatus:
        raise NotImplementedError

    @abstractmethod
    def prepare(self) -> Deferred:
        raise NotImplementedError

    @abstractmethod
    def cleanup(self) -> Deferred:
        raise NotImplementedError

    @abstractmethod
    def metadata(self) -> EnvMetadata:
        raise NotImplementedError

    @abstractmethod
    def config(self) -> EnvConfig:
        raise NotImplementedError

    @abstractmethod
    def update_config(self, config: EnvConfig) -> None:
        raise NotImplementedError

    @abstractmethod
    def listen(self, event_id: EnvEventId,
               callback: Callable[[EnvEvent], Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def runtime(self, payload: Payload, config: Optional[EnvConfig]) \
            -> Runtime:
        raise NotImplementedError


class EnvironmentManager:

    def __init__(self):
        self._envs: Dict[EnvId, Environment] = {}
        self._state: Dict[EnvId, bool] = {}

    def register_env(self, env: Environment) -> None:
        env_id = env.metadata().id
        self._envs[env_id] = env
        self._state[env_id] = False

    def state(self) -> Dict[EnvId, bool]:
        return dict(self._state)

    def set_state(self, state: Dict[EnvId, bool]) -> None:
        for env_id, enabled in state.items():
            self.set_enabled(env_id, enabled)

    def enabled(self, env_id: EnvId) -> bool:
        return self._state[env_id]

    def set_enabled(self, env_id: EnvId, enabled: bool) -> None:
        if env_id in self._state:
            self._state[env_id] = enabled

    def environments(self) -> List[Environment]:
        return list(self._envs.values())

    def environment(self, env_id: EnvId) -> Environment:
        return self._envs[env_id]
