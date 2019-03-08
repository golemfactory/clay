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


class Environment(ABC):

    @classmethod
    @abstractmethod
    def supported(cls) -> EnvSupportStatus:
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

    def state(self) -> Dict[EnvId, bool]:
        raise NotImplementedError

    def set_state(self, state: Dict[EnvId, bool]) -> None:
        raise NotImplementedError

    def enabled(self, env_id: EnvId) -> bool:
        raise NotImplementedError

    def set_enabled(self, env_id: EnvId, enabled: bool) -> None:
        raise NotImplementedError

    def environments(self) -> List[Environment]:
        raise NotImplementedError

    def environment(self, env_id: EnvId) -> Environment:
        raise NotImplementedError

