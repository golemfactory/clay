import time
from abc import ABC, abstractmethod
from copy import deepcopy
from enum import Enum
from logging import Logger, getLogger
from threading import RLock

from typing import Any, Callable, Dict, List, Optional, NamedTuple, Union, \
    Sequence, Iterable, ContextManager, Set, Tuple

from dataclasses import dataclass, field
from twisted.internet.defer import Deferred
from twisted.internet.threads import deferToThread
from twisted.python.failure import Failure

from golem.core.simpleserializer import DictSerializable
from golem.model import Performance


class UsageCounter(Enum):
    CLOCK_MS = 'clock_ms'

    CPU_TOTAL_NS = 'cpu_total_ns'
    CPU_USER_NS = 'cpu_user_ns'
    CPU_KERNEL_NS = 'cpu_kernel_ns'

    RAM_MAX_BYTES = 'ram_max_bytes'
    RAM_AVG_BYTES = 'ram_avg_bytes'


@dataclass
class UsageCounterValues:
    clock_ms: float = 0.0

    cpu_total_ns: float = 0.0
    cpu_user_ns: float = 0.0
    cpu_kernel_ns: float = 0.0

    ram_max_bytes: int = 0
    ram_avg_bytes: float = 0.0


EnvId = str
RuntimeId = str


class RuntimeEventType(Enum):
    PREPARED = 1
    STARTED = 2
    STOPPED = 3
    TORN_DOWN = 4
    ERROR_OCCURRED = 5


class RuntimeEvent(NamedTuple):
    type: RuntimeEventType
    details: Optional[Dict[str, Any]] = None


RuntimeEventListener = Callable[[RuntimeEvent], Any]


class EnvEventType(Enum):
    ENABLED = 1
    DISABLED = 2
    PREREQUISITES_INSTALLED = 3
    CONFIG_UPDATED = 4
    ERROR_OCCURRED = 5

    def __str__(self) -> str:
        return self.name


class EnvEvent(NamedTuple):
    type: EnvEventType
    details: Optional[Dict[str, Any]] = None


EnvEventListener = Callable[[EnvEvent], Any]


class EnvConfig(DictSerializable, ABC):
    """ Environment-wide configuration. Specifies e.g. available resources. """


class Prerequisites(DictSerializable, ABC):
    """
    Environment-specific requirements for computing a task. Distributed with the
    task header. Providers are expected to prepare (download, install, etc.)
    prerequisites in advance not to waste computation time.
    """


class RuntimePayload(ABC):
    """ A set of necessary data required to create a Runtime. """


class EnvSupportStatus(NamedTuple):
    """ Is the environment supported? If not, why? """
    supported: bool
    nonsupport_reason: Optional[str] = None


@dataclass
class BenchmarkResult:
    performance: float = 0.0
    cpu_usage: int = Performance.DEFAULT_CPU_USAGE

    @staticmethod
    def from_performance(performance: Performance):
        return BenchmarkResult(performance.value, performance.cpu_usage)


class RuntimeStatus(Enum):
    CREATED = 0
    PREPARING = 1
    PREPARED = 2
    STARTING = 3
    RUNNING = 4
    STOPPED = 5
    CLEANING_UP = 6
    TORN_DOWN = 7
    FAILURE = 8

    def __str__(self) -> str:
        return self.name


class RuntimeInput(ContextManager['RuntimeInput'], ABC):
    """ A handle for writing to standard input stream of a running Runtime.
        Input could be either raw (bytes) or encoded (str). Could be used as a
        context manager to call .close() automatically. """

    def __init__(self, encoding: Optional[str] = None) -> None:
        self._encoding = encoding

    def _encode(self, line: Union[str, bytes]) -> bytes:
        """ Encode given data (if needed). If the Input is encoded it expects
            the argument to be str, otherwise bytes is expected. """
        if self._encoding:
            assert isinstance(line, str)
            return line.encode(self._encoding)
        assert isinstance(line, bytes)
        return line

    @abstractmethod
    def write(self, data: Union[str, bytes]) -> None:
        """ Write data to the stream. Raw input would accept only str while
            encoded input only bytes. An attempt to write to a closed input
            would rise an error. """
        raise NotImplementedError

    @abstractmethod
    def close(self):
        """ Close the input and send EOF to the Runtime. Calling this method on
            a closed input won't do anything.
            NOTE: If there are many open input handles for a single Runtime
            then closing one of them will effectively close all the other. """
        raise NotImplementedError

    def __enter__(self) -> 'RuntimeInput':
        return self

    def __exit__(self, *_, **__) -> None:
        self.close()


RuntimeOutput = Iterable[Union[str, bytes]]


class RuntimeOutputBase(RuntimeOutput, ABC):
    """ A handle for reading output (either stdout or stderr) from a running
        Runtime. Yielded items are output lines. Output could be either raw
        (bytes) or decoded (str). """

    def __init__(self, encoding: Optional[str] = None) -> None:
        self._encoding = encoding

    def _decode(self, line: bytes) -> Union[str, bytes]:
        if self._encoding:
            return line.decode(self._encoding)
        return line


class Runtime(ABC):
    """ A runnable object representing some particular computation. Tied to a
        particular Environment that was used to create this object. """

    @abstractmethod
    def id(self) -> Optional[RuntimeId]:
        """ Get unique identifier of this Runtime. Might not be available if the
            Runtime is not yet prepared. """
        raise NotImplementedError

    @abstractmethod
    def prepare(self) -> Deferred:
        """ Prepare the Runtime to be started. Assumes current status is
            'CREATED'. """
        raise NotImplementedError

    @abstractmethod
    def clean_up(self) -> Deferred:
        """ Clean up after the Runtime has finished running. Assumes current
            status is 'STOPPED' or 'FAILURE'. In the latter case it is not
            guaranteed that the cleanup will be successful. """
        raise NotImplementedError

    @abstractmethod
    def start(self) -> Deferred:
        """ Start the computation. Assumes current status is 'PREPARED'. """
        raise NotImplementedError

    @abstractmethod
    def wait_until_stopped(self) -> Deferred:
        """ Can be called after calling `start` to wait until the runtime has
            stopped """
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> Deferred:
        """ Interrupt the computation. Assumes current status is 'RUNNING'. """
        raise NotImplementedError

    def status(self) -> RuntimeStatus:
        """ Get the current status of the Runtime. """
        raise NotImplementedError

    @abstractmethod
    def stdin(self, encoding: Optional[str] = None) -> RuntimeInput:
        """ Get STDIN stream of the Runtime. If encoding is None the returned
            stream will be raw (accepting bytes), otherwise it will be encoded
            (accepting str). Assumes current status is 'PREPARED', 'STARTING',
            or 'RUNNING'. """
        raise NotImplementedError

    @abstractmethod
    def stdout(self, encoding: Optional[str] = None) -> RuntimeOutput:
        """ Get STDOUT stream of the Runtime. If encoding is None the returned
            stream will be raw (bytes), otherwise it will be decoded (str).
            Assumes current status is one of the following: 'PREPARED',
            'STARTING', 'RUNNING', 'STOPPED', or 'FAILURE' (however, in the
            last case output might not be available). """
        raise NotImplementedError

    @abstractmethod
    def stderr(self, encoding: Optional[str] = None) -> RuntimeOutput:
        """ Get STDERR stream of the Runtime. If encoding is None the returned
            stream will be raw (bytes), otherwise it will be decoded (str).
            Assumes current status is 'RUNNING', 'STOPPED', or 'FAILURE'
            (however, in the last case output might not be available). """
        raise NotImplementedError

    @abstractmethod
    def get_port_mapping(self, port: int) -> Tuple[str, int]:
        """
        After a runtime is created with exposed ports this function should
        return a valid socket address where the initial port is accessible from.
        """
        raise NotImplementedError

    @abstractmethod
    def usage_counter_values(self) -> UsageCounterValues:
        """ For each usage counter supported by the Environment (e.g. clock
            time) get current usage by this Runtime. """
        raise NotImplementedError

    def listen(self, event_type: RuntimeEventType,
               listener: RuntimeEventListener) -> None:
        """ Register a listener for a given type of Runtime events. """
        raise NotImplementedError


class RuntimeBase(Runtime, ABC):

    def __init__(self, logger: Optional[Logger] = None) -> None:
        self._logger = logger or getLogger(__name__)
        self._status = RuntimeStatus.CREATED
        self._status_lock = RLock()
        self._event_listeners: \
            Dict[RuntimeEventType, Set[RuntimeEventListener]] = {}

    @staticmethod
    def _assert_status(
            actual: RuntimeStatus,
            expected: Union[RuntimeStatus, Sequence[RuntimeStatus]]
    ) -> None:
        """ Assert that actual status is one of the expected. """

        if isinstance(expected, RuntimeStatus):
            expected = [expected]

        if actual not in expected:
            exp_str = " or ".join(map(str, expected))
            raise ValueError(
                f"Invalid status: {actual}. Expected: {exp_str}")

    def _change_status(
            self,
            from_status: Union[RuntimeStatus, Sequence[RuntimeStatus]],
            to_status: RuntimeStatus
    ) -> None:
        """ Assert that current Runtime status is the given one and change to
            another one. Using lock to ensure atomicity. """

        with self._status_lock:
            self._assert_status(self._status, from_status)
            self._status = to_status

    def _set_status(self, status) -> None:
        with self._status_lock:
            self._status = status

    def _emit_event(
            self,
            event_type: RuntimeEventType,
            details: Optional[Dict[str, Any]] = None
    ) -> None:
        """ Create an event with the given type and details and send a copy to
            every listener registered for this type of events. """

        event = RuntimeEvent(
            type=event_type,
            details=details
        )
        self._logger.debug("Emit event: %r", event)

        def _handler_error_callback(failure):
            self._logger.error(
                "Error occurred in event handler.", exc_info=failure.value)

        for listener in self._event_listeners.get(event_type, ()):
            deferred = deferToThread(listener, deepcopy(event))
            deferred.addErrback(_handler_error_callback)

    def _prepared(self, *_) -> None:
        """ Acknowledge that Runtime has been prepared. Log message, set status
            and emit event. Arguments are ignored (for callback use). """
        self._logger.info("Runtime prepared.")
        self._set_status(RuntimeStatus.PREPARED)
        self._emit_event(RuntimeEventType.PREPARED)

    def _started(self, *_) -> None:
        """ Acknowledge that Runtime has been started. Log message, set status
            and emit event. Arguments are ignored (for callback use). """
        self._logger.info("Runtime started.")
        self._set_status(RuntimeStatus.RUNNING)
        self._emit_event(RuntimeEventType.STARTED)

    def _stopped(self, *_) -> None:
        """ Acknowledge that Runtime has been stopped. Log message, set status
            and emit event. Arguments are ignored (for callback use). """
        self._logger.info("Runtime stopped.")
        self._set_status(RuntimeStatus.STOPPED)
        self._emit_event(RuntimeEventType.STOPPED)

    def _torn_down(self, *_) -> None:
        """ Acknowledge that Runtime has been torn down. Log message, set status
            and emit event. Arguments are ignored (for callback use). """
        self._logger.info("Runtime torn down.")
        self._set_status(RuntimeStatus.TORN_DOWN)
        self._emit_event(RuntimeEventType.TORN_DOWN)

    def _error_occurred(
            self,
            error: Optional[Exception],
            message: str,
            set_status: bool = True
    ) -> None:
        """ Acknowledge that an error occurred in runtime. Log message and emit
            event. If set_status is True also set status to 'FAILURE'. """
        self._logger.error(message, exc_info=error)
        if set_status:
            self._set_status(RuntimeStatus.FAILURE)
        self._emit_event(
            RuntimeEventType.ERROR_OCCURRED, {
                'error': error,
                'message': message
            })

    def _error_callback(self, message: str) -> Callable[[Failure], Failure]:
        """ Get an error callback accepting Twisted's Failure object that will
            call _error_occurred(). """
        def _callback(failure):
            self._error_occurred(failure.value, message)
            return failure
        return _callback

    def status(self) -> RuntimeStatus:
        with self._status_lock:
            return self._status

    def listen(
            self,
            event_type: RuntimeEventType,
            listener: RuntimeEventListener
    ) -> None:
        self._event_listeners.setdefault(event_type, set()).add(listener)

    def wait_until_stopped(self) -> Deferred:
        """ Can be called after calling `start` to wait until the runtime has
            stopped """
        def _wait_until_stopped():
            while self.status() == RuntimeStatus.RUNNING:
                time.sleep(1)
        return deferToThread(_wait_until_stopped)


@dataclass
class EnvMetadata:
    id: EnvId
    description: str = ''
    custom_metadata: Dict[str, Any] = field(default_factory=dict)


class EnvStatus(Enum):
    DISABLED = 0
    PREPARING = 1
    ENABLED = 2
    CLEANING_UP = 3
    ERROR = 4

    def __str__(self) -> str:
        return self.name


class Environment(ABC):
    """ An Environment capable of running computations. It is responsible for
        creating Runtimes. """

    @classmethod
    @abstractmethod
    def supported(cls) -> EnvSupportStatus:
        """ Is the Environment supported on this machine? """
        raise NotImplementedError

    @abstractmethod
    def status(self) -> EnvStatus:
        """ Get current status of the Environment. """
        raise NotImplementedError

    @abstractmethod
    def prepare(self) -> Deferred:
        """ Activate the Environment. Assumes current status is 'DISABLED'. """
        raise NotImplementedError

    @abstractmethod
    def clean_up(self) -> Deferred:
        """ Deactivate the Environment. Assumes current status is 'ENABLED' or
            'ERROR'. """
        raise NotImplementedError

    @abstractmethod
    def run_benchmark(self) -> Deferred:
        """ Get the general performance score for this environment. """
        raise NotImplementedError

    @abstractmethod
    def parse_prerequisites(self, prerequisites_dict: Dict[str, Any]) \
            -> Prerequisites:
        """ Build Prerequisites struct from supplied dictionary. Returned value
            is of appropriate type for calling install_prerequisites(). """
        raise NotImplementedError

    @abstractmethod
    def install_prerequisites(self, prerequisites: Prerequisites) -> Deferred:
        """ Prepare Prerequisites for running a computation. Assumes current
            status is 'ENABLED'.
            Returns boolean indicating whether installation was successful. """
        raise NotImplementedError

    @abstractmethod
    def parse_config(self, config_dict: Dict[str, Any]) -> EnvConfig:
        """ Build config struct from supplied dictionary. Returned value
            is of appropriate type for calling update_config(). """
        raise NotImplementedError

    @abstractmethod
    def config(self) -> EnvConfig:
        """ Get current configuration of the Environment. """
        raise NotImplementedError

    @abstractmethod
    def update_config(self, config: EnvConfig) -> None:
        """ Update configuration. Assumes current status is 'DISABLED'. """
        raise NotImplementedError

    @abstractmethod
    def listen(
            self,
            event_type: EnvEventType,
            listener: EnvEventListener
    ) -> None:
        """ Register a listener for a given type of Environment events. """
        raise NotImplementedError

    def supported_usage_counters(self) -> List[UsageCounter]:
        """ Get list of usage counters supported by this environment. """
        raise NotImplementedError

    @abstractmethod
    def runtime(
            self,
            payload: RuntimePayload,
            config: Optional[EnvConfig] = None
    ) -> Runtime:
        """ Create a Runtime from the given Payload. Optionally, share the
            specified directory with the created Runtime. Optionally, override
            current config with the supplied one (it is however not guaranteed
            that all config parameters could be overridden). Assumes current
            status is 'ENABLED'. """
        raise NotImplementedError


class EnvironmentBase(Environment, ABC):

    def __init__(self, logger: Optional[Logger] = None) -> None:
        self._status = EnvStatus.DISABLED
        self._logger = logger or getLogger(__name__)
        self._event_listeners: Dict[EnvEventType, Set[EnvEventListener]] = {}

    def _emit_event(
            self,
            event_type: EnvEventType,
            details: Optional[Dict[str, Any]] = None
    ) -> None:
        """ Create an event with the given type and details and send a copy to
            every listener registered for this type of events. """

        event = EnvEvent(
            type=event_type,
            details=details
        )
        self._logger.debug("Emit event: %r", event)

        def _handler_error_callback(failure):
            self._logger.error(
                "Error occurred in event handler.", exc_info=failure.value)

        for listener in self._event_listeners.get(event_type, ()):
            deferred = deferToThread(listener, deepcopy(event))
            deferred.addErrback(_handler_error_callback)

    def _env_enabled(self) -> None:
        """ Acknowledge that Runtime has been enabled. Log message, set status
            and emit event. Arguments are ignored (for callback use). """
        self._logger.info("Environment enabled.")
        self._status = EnvStatus.ENABLED
        self._emit_event(EnvEventType.ENABLED)

    def _env_disabled(self) -> None:
        """ Acknowledge that Runtime has been disabled. Log message, set status
            and emit event. Arguments are ignored (for callback use). """
        self._logger.info("Environment disabled.")
        self._status = EnvStatus.DISABLED
        self._emit_event(EnvEventType.DISABLED)

    def _config_updated(self, config: EnvConfig) -> None:
        """ Acknowledge that Runtime's config has been updated. Log message and
            emit event. The updated config is included in event's details. """
        self._logger.info("Configuration updated.")
        self._emit_event(EnvEventType.CONFIG_UPDATED, {'config': config})

    def _prerequisites_installed(self, prerequisites: Prerequisites) -> None:
        """ Acknowledge that Prerequisites have been installed. Log message and
            emit event. The installed prerequisites are included in event's
            details. """
        self._logger.info("Prerequisites installed.")
        self._emit_event(
            EnvEventType.PREREQUISITES_INSTALLED,
            {'prerequisites': prerequisites})

    def _error_occurred(
            self,
            error: Optional[Exception],
            message: str,
            set_status: bool = True
    ) -> None:
        """ Acknowledge that an error occurred in runtime. Log message and emit
            event. If set_status is True also set status to 'FAILURE'. """
        self._logger.error(message, exc_info=error)
        if set_status:
            self._status = EnvStatus.ERROR
        self._emit_event(
            EnvEventType.ERROR_OCCURRED, {
                'error': error,
                'message': message
            })

    def status(self) -> EnvStatus:
        """ Get current status of the Environment. """
        return self._status

    def listen(
            self,
            event_type: EnvEventType,
            listener: EnvEventListener
    ) -> None:
        self._event_listeners.setdefault(event_type, set()).add(listener)
