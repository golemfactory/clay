import functools
import inspect
import logging
import sys
import uuid

from abc import abstractmethod, ABCMeta
from multiprocessing import Process
from multiprocessing.connection import Connection
from typing import Optional, List, Any, Dict, Callable, Type, Tuple, Union, \
    Collection

from twisted.internet.defer import Deferred
from twisted.python.failure import Failure

from golem.core.service import IService, ThreadedService
from golem.ipc.serializer import IPCMessageSerializer
from golem.ipc.serializer.thrift import ThriftMessageSerializer

logger = logging.getLogger(__name__)


class ProcessService(IService):

    def __init__(self, data_dir: str) -> None:
        self._data_dir = data_dir
        self._process: Optional[Process] = None

    def start(self) -> None:
        if self._process:
            raise RuntimeError('process already spawned')

        args = [self._data_dir] + self._get_spawn_arguments()

        self._process = Process(target=self._spawn, args=args)
        self._process.daemon = True
        self._process.start()

    def stop(self) -> None:
        if not self._process:
            return

        process = self._process
        self._process = None
        process.terminate()
        process.join()

    def running(self) -> bool:
        if not self._process:
            return False
        return self._process.is_alive()

    @classmethod
    def _spawn(cls, data_dir: str, *args) -> None:
        """ Called in a new process """

    @abstractmethod
    def _get_spawn_arguments(self) -> List[Any]:
        pass


class IPCService(ThreadedService, metaclass=ABCMeta):

    POLL_TIMEOUT = 0.5  # s

    MSG_NAMES: Dict[str, Union[Type, Callable]] = dict()

    def __init__(self,
                 read_conn: Connection,
                 write_conn: Connection,
                 serializer: Optional[IPCMessageSerializer] = None,
                 ) -> None:

        ThreadedService.__init__(self)

        self._read_conn = read_conn
        self._write_conn = write_conn
        self._serializer = serializer or self._default_serializer()

    @staticmethod
    def build_message_map(module_name: str,
                          excluded: str = 'thrift') -> Dict[str, Type]:
        return {
            name: cls for name, cls in inspect.getmembers(
                sys.modules[module_name],
                lambda cls: (inspect.isclass(cls)
                             and not cls.__module__.startswith(excluded))
            )
        }

    @staticmethod
    def _default_serializer() -> IPCMessageSerializer:
        return ThriftMessageSerializer()

    @abstractmethod
    def on_message(self, request_id: bytes, msg: object) -> None:
        """ Handle messages """

    @abstractmethod
    def on_close(self, error: Optional[Exception] = None) -> None:
        """ Handle connection closed event """

    @abstractmethod
    def on_error(self, error: Optional[Exception] = None) -> None:
        """ Handle serialization and format error events """

    def _loop(self) -> None:
        """ Main service loop """

        try:
            request_id, msg = self._read()
        except Exception as exc:  # pylint: disable=broad-except
            self.on_error(exc)
        else:
            if msg:
                self.on_message(request_id, msg)

    def _read(self, **options) -> Tuple[Optional[bytes], Optional[object]]:
        """ Read and deserialize data from a pipe """
        empty = None, None

        # poll and read
        try:
            if self._read_conn.poll(self.POLL_TIMEOUT):
                data = self._read_conn.recv_bytes()
            else:
                return empty
        except EOFError as exc:
            self.on_close(exc)
            return empty

        # deserialize
        try:
            return self._serializer.deserialize(
                data,
                msg_types=self.MSG_NAMES,
                **options
            )
        except Exception as exc:  # pylint: disable=broad-except
            self.on_error(exc)
            return empty

    def _write(self, msg: object, **options) -> bool:
        """ Serialize and write data to a pipe """

        # serialize
        try:
            serialized = self._serializer.serialize(msg, **options)
        except Exception as exc:  # pylint: disable=broad-except
            self.on_error(exc)
            return False

        # write
        try:
            self._write_conn.send_bytes(serialized)
        except EOFError as exc:
            self.on_close(exc)
            return False

        return True


class RPCMixin(metaclass=ABCMeta):

    REQ_MSG_BUILDERS: Dict[str, Union[Type, Callable]] = dict()
    RES_MSG_BUILDERS: Dict[str, Union[Type, Callable]] = dict()

    METHOD_MAP: Dict[Type, str] = dict()  # msg class to fn name

    FROM_PY: Dict[Type, Callable] = dict()  # arg class converters
    TO_PY: Dict[Type, Callable] = dict()  # arg class converters

    @abstractmethod
    def _build_msg(self,
                   fn_name: str,
                   *args,
                   **kwargs) -> object:
        """ Build a message """

    @staticmethod
    def _new_request_id() -> bytes:
        return str(uuid.uuid4()).encode()

    @staticmethod
    def _convert_types(source: Dict[str, Any],
                       converters: Dict[Type, Callable]) -> Dict[str, Any]:

        return _convert_dict(source, converters)


class IPCClientService(IPCService, RPCMixin, metaclass=ABCMeta):

    def __init__(self,
                 read_conn: Connection,
                 write_conn: Connection,
                 serializer: Optional[IPCMessageSerializer] = None,
                 ) -> None:

        IPCService.__init__(self, read_conn, write_conn, serializer=serializer)

        self._requests: Dict[bytes, Deferred] = dict()  # deferred requests
        self._functions: Dict[str, functools.partial] = dict()  # proxy funcs

    def __getattribute__(self, item: str) -> Any:
        """
        Create and return a proxy function for any method in METHODS;
        return all other properties as-is.
        """

        if item != 'REQ_MSG_BUILDERS' and item in self.REQ_MSG_BUILDERS:
            if item not in self._functions:
                self._functions[item] = functools.partial(self._request, item)
            return self._functions[item]

        return super().__getattribute__(item)

    def on_close(self, error: Optional[Exception] = None) -> None:
        super().on_close(error)
        self._requests = dict()

    def on_response(self, request_id: bytes, data: Any) -> None:

        if request_id not in self._requests:
            error = RuntimeError('Unknown request_id {} for response: {}'
                                 .format(request_id, data))
            return self.on_error(error)

        deferred = self._requests.pop(request_id)

        if isinstance(data, (Exception, Failure)):
            fn = deferred.errback
        else:
            fn = deferred.callback

        fn(data)

    def _build_msg(self,
                   fn_name: str,
                   *args,
                   **kwargs) -> object:

        fn_args, _ = self._get_method_spec(fn_name)
        call_kwargs = kwargs

        # positional arguments from specification
        for i, fn_arg in enumerate(fn_args or []):
            if i == len(args):
                break
            call_kwargs[fn_arg] = args[i]

        call_kwargs = self._convert_types(kwargs, self.FROM_PY)
        msg_builder = self.REQ_MSG_BUILDERS[fn_name]
        return msg_builder(**call_kwargs)

    def _request(self, fn_name: str, *args, **kwargs) -> Deferred:

        request_id = self._new_request_id()
        msg = self._build_msg(fn_name, *args, **kwargs)

        deferred = Deferred()

        if self._write(msg, request_id=request_id):
            self._requests[request_id] = deferred
        else:
            error = RuntimeError('Pipe write failed for call: {}'.format(msg))
            deferred.errback(error)

        return deferred

    @abstractmethod
    def _get_method_spec(self, method_name: str) -> Tuple[Optional[List[str]],
                                                          Optional[List[str]]]:
        """ Return (args, kwargs) tuple of function arguments """


class IPCServerService(IPCService, RPCMixin, metaclass=ABCMeta):

    def __init__(self,  # noqa pylint: disable=too-many-arguments
                 read_conn: Connection,
                 write_conn: Connection,
                 proxy_object: object,
                 serializer: Optional[IPCMessageSerializer] = None,
                 ) -> None:

        IPCService.__init__(self, read_conn, write_conn, serializer=serializer)

        # request fn name to method map
        self._functions = {k: getattr(proxy_object, k) for k
                           in self.REQ_MSG_BUILDERS.keys()}

    def on_request(self, request_id: bytes, msg: object) -> None:

        properties = self._convert_types(msg.__dict__, self.TO_PY)
        fn_name = self.METHOD_MAP[msg.__class__]
        fn = self._functions[fn_name]

        def done(result):
            if isinstance(result, Deferred):
                result.addBoth(lambda r: self._respond(request_id, fn_name, r))
            else:
                self._respond(request_id, fn_name, result)

        def call():
            try:
                result = fn(**properties)
            except Exception as exc:  # pylint: disable=broad-except
                result = exc
            done(result)

        logger.debug('IPC server call: %r(**%r)', fn_name, properties)
        self._execute(call)

    def _build_msg(self,
                   fn_name: str,
                   *args,
                   **kwargs) -> object:

        msg_builder = self.RES_MSG_BUILDERS[fn_name]
        return msg_builder(*args, **kwargs)

    def _respond(self,
                 request_id: bytes,
                 fn_name: str,
                 result: Any) -> None:

        logger.debug('IPC server response: %r, %r, %r',
                     request_id, fn_name, result)

        if isinstance(result, (Exception, Failure)):
            msg = self._build_error_msg(fn_name, result)
        else:
            msg = self._build_msg(fn_name, result)

        self._write(msg, request_id=request_id)

    @abstractmethod
    def _build_error_msg(self,
                         fn_name: str,
                         result: Any) -> object:
        pass

    @abstractmethod
    def _execute(self, fn: Callable) -> Any:
        """ Execute a function in a chosen context """


def _convert_dict(src: Dict, converters: Dict[Type, Callable]):
    result = {}

    for k, v in src.items():

        if isinstance(v, dict):
            result[k] = _convert_dict(v, converters)
        elif not isinstance(v, str) and isinstance(v, Collection):
            result[k] = _convert_coll(v, converters)
        elif v.__class__ in converters:
            result[k] = converters[v.__class__](v)
        else:
            result[k] = v

    return result


def _convert_coll(src: Collection, converters: Dict[Type, Callable]):
    return src.__class__([
        converters[elem.__class__](elem) if elem.__class__ in converters
        else elem
        for elem in src
    ])

