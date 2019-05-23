from abc import ABC, abstractmethod
from copy import deepcopy
from enum import Enum
from logging import Logger, getLogger
from threading import RLock
from pathlib import Path

from typing import Any, Callable, Dict, List, Optional, NamedTuple, Union, \
    Sequence, Iterable, ContextManager, Set

from twisted.internet.defer import Deferred
from twisted.internet.threads import deferToThread
from twisted.python.failure import Failure

from golem.core.simpleserializer import DictSerializable

CounterId = str
CounterUsage = Any

EnvId = str


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
    env_id: EnvId
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


class Payload(DictSerializable, ABC):
    """
    A definition for Runtime. Environment-specific description of computation to
    be run. Received when provider is assigned a subtask.
    """


class EnvSupportStatus(NamedTuple):
    """ Is the environment supported? If not, why? """
    supported: bool
    nonsupport_reason: Optional[str] = None


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

    def __enter__(self) -> 'RuntimeInput':
        return self

    def __exit__(self, *_, **__) -> None:
        self.close()


class RuntimeOutput(Iterable[Union[str, bytes]], ABC):
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

    def __init__(self, logger: Optional[Logger] = None) -> None:
        self._logger = logger or getLogger(__name__)
        self._status = RuntimeStatus.CREATED
        self._status_lock = RLock()
        self._event_listeners: \
            Dict[RuntimeEventType, Set[RuntimeEventListener]] = {}

    @staticmethod
    def _assert_status(
            actual: RuntimeStatus,
            expected: Union[RuntimeStatus, Sequence[RuntimeStatus]]) -> None:
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
            to_status: RuntimeStatus) -> None:
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
    def stop(self) -> Deferred:
        """ Interrupt the computation. Assumes current status is 'RUNNING'. """
        raise NotImplementedError

    def status(self) -> RuntimeStatus:
        """ Get the current status of the Runtime. """
        with self._status_lock:
            return self._status

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
    def usage_counters(self) -> Dict[CounterId, CounterUsage]:
        """ For each usage counter supported by the Environment (e.g. clock
            time) get current usage by this Runtime. """
        raise NotImplementedError

    def listen(self, event_type: RuntimeEventType,
               listener: RuntimeEventListener) -> None:
        """ Register a listener for a given type of Runtime events. """
        self._event_listeners.setdefault(event_type, set()).add(listener)

    @abstractmethod
    def call(self, alias: str, *args, **kwargs) -> Deferred:
        """ Send RPC call to the Runtime. """
        raise NotImplementedError


class EnvMetadata(NamedTuple):
    id: EnvId
    description: str
    supported_counters: List[CounterId]
    custom_metadata: Dict[str, Any]


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
            env_id=self.metadata().id,
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

    @classmethod
    @abstractmethod
    def supported(cls) -> EnvSupportStatus:
        """ Is the Environment supported on this machine? """
        raise NotImplementedError

    def status(self) -> EnvStatus:
        """ Get current status of the Environment. """
        return self._status

    @abstractmethod
    def prepare(self) -> Deferred:
        """ Activate the Environment. Assumes current status is 'DISABLED'. """
        raise NotImplementedError

    @abstractmethod
    def clean_up(self) -> Deferred:
        """ Deactivate the Environment. Assumes current status is 'ENABLED' or
            'ERROR'. """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def metadata(cls) -> EnvMetadata:
        """ Get Environment metadata. """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def parse_prerequisites(cls, prerequisites_dict: Dict[str, Any]) \
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

    @classmethod
    @abstractmethod
    def parse_config(cls, config_dict: Dict[str, Any]) -> EnvConfig:
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

    def listen(self, event_type: EnvEventType, listener: EnvEventListener) \
            -> None:
        """ Register a listener for a given type of Environment events. """
        self._event_listeners.setdefault(event_type, set()).add(listener)

    @classmethod
    @abstractmethod
    def parse_payload(cls, payload_dict: Dict[str, Any]) -> Payload:
        """ Build Payload struct from supplied dictionary. Returned value
            is of appropriate type for calling runtime(). """
        raise NotImplementedError

    @abstractmethod
    def runtime(
            self,
            payload: Payload,
            shared_dir: Optional[Path] = None,
            config: Optional[EnvConfig] = None
    ) -> Runtime:
        """ Create a Runtime from the given Payload. Optionally, share the
            specified directory with the created Runtime. Optionally, override
            current config with the supplied one (it is however not guaranteed
            that all config parameters could be overridden). Assumes current
            status is 'ENABLED'. """
        raise NotImplementedError
