import functools
import os

from abc import abstractmethod, ABCMeta
from multiprocessing import Process
from multiprocessing.connection import Connection
from typing import Optional, List, Any, Dict, Set, Callable, Type, Tuple

from twisted.internet.defer import Deferred
from twisted.python.failure import Failure

from golem.core.service import IService, ThreadedService
from golem.ipc.serializer import IPCMessageSerializer
from golem.ipc.serializer.thrift import ThriftMessageSerializer


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

    MSG_MAP: Dict[str, Type] = dict()  # message name to msg class
    METHOD_MAP: Dict[str, Type] = dict()  # function name to msg class

    def __init__(self,
                 read_conn: Connection,
                 write_conn: Connection,
                 serializer: Optional[IPCMessageSerializer] = None,
                 ) -> None:

        super().__init__()

        self._read_conn = read_conn
        self._write_conn = write_conn
        self._serializer = serializer or self._default_serializer()

    @staticmethod
    def _default_serializer() -> IPCMessageSerializer:
        return ThriftMessageSerializer()

    @abstractmethod
    def _on_message(self, msg: object) -> None:
        """ Handle messages """

    @abstractmethod
    def _on_close(self, error: Optional[Exception] = None) -> None:
        """ Handle connection closed event """

    @abstractmethod
    def _on_error(self, error: Optional[Exception] = None) -> None:
        """ Handle serialization and format error events """

    @abstractmethod
    def _get_method_spec(self, method_name: str) -> Tuple[Optional[List[str]],
                                                          Optional[List[str]]]:
        """ Return a (args, kwargs) tuple of function argument names """

    def _loop(self) -> None:
        """ Main service loop """

        try:
            msg: Optional[object] = self._read()
        except Exception as exc:  # pylint: disable=broad-except
            self._on_error(exc)
        else:
            if msg:
                self._on_message(msg)

    def _build_msg(self,
                   request_id: bytes,
                   fn_name: str,
                   *args,
                   **kwargs) -> object:

        """ Build a message, basing on the fn_name and the method map """

        fn_spec = self._get_method_spec(fn_name)
        call_kwargs = {'request_id': request_id}

        # positional arguments present in function def
        if fn_spec[0]:
            for i, arg in enumerate(fn_spec[0]):
                call_kwargs[arg] = args[i]

        # keyword arguments present in function def
        if fn_spec[1]:
            call_kwargs.update(kwargs)

        msg_cls = self.METHOD_MAP[fn_name]
        return msg_cls(**call_kwargs)

    def _read(self, **options) -> object:
        """ Read and deserialize data from a pipe """

        # Poll for data and read if any
        try:
            if self._read_conn.poll(self.POLL_TIMEOUT):
                data = self._read_conn.recv_bytes()
            else:
                return None
        except EOFError as exc:
            self._on_close(exc)
            return None

        # Deserialize data
        try:
            return self._serializer.deserialize(
                data,
                msg_types=self.MSG_MAP,
                **options
            )
        except Exception as exc:  # pylint: disable=broad-except
            self._on_error(exc)
            return None

    def _write(self, msg: object, **options) -> bool:
        """ Serialize and write data to a pipe """

        # Serialize data
        try:
            serialized = self._serializer.serialize(msg, **options)
        except Exception as exc:  # pylint: disable=broad-except
            self._on_error(exc)
            return False

        # Send serialized data
        try:
            self._write_conn.send_bytes(serialized)
        except EOFError as exc:
            self._on_close(exc)
            return False

        return True


class IPCServerService(IPCService, metaclass=ABCMeta):

    def __init__(self,
                 read_conn: Connection,
                 write_conn: Connection,
                 serializer: Optional[IPCMessageSerializer] = None,
                 ) -> None:

        super().__init__(read_conn, write_conn, serializer=serializer)

        self._requests: Dict[bytes, Deferred] = dict()  # deferred requests
        self._functions: Dict[str, functools.partial] = dict()  # proxy funcs

    def __getattribute__(self, item: str) -> Any:
        """
        Create and return a proxy function for any method in METHODS;
        return all other properties as-is.
        """

        if item != 'METHODS' and item in self.METHOD_MAP.keys():
            if item not in self._functions:
                self._functions[item] = functools.partial(self._request, item)
            return self._functions[item]

        return super().__getattribute__(item)

    def _request(self, fn_name: str, *args, **kwargs) -> Deferred:

        request_id = os.urandom(16)
        msg = self._build_msg(request_id, fn_name, *args, **kwargs)

        deferred = Deferred()

        if self._write(msg):
            self._requests[request_id] = deferred
        else:
            error = RuntimeError('Pipe write failed for call: {}'.format(msg))
            deferred.errback(error)

        return deferred

    def _on_response(self, request_id: bytes, data: Any) -> None:

        if request_id not in self._requests:
            error = RuntimeError('Unknown request_id {} for response {}'
                                 .format(request_id, data))
            self._on_error(error)
            return

        deferred = self._requests.pop(request_id)

        if isinstance(data, (Exception, Failure)):
            fn = deferred.errback
        else:
            fn = deferred.callback

        fn(data)

    def _on_close(self, error: Optional[Exception] = None) -> None:
        super()._on_close(error)
        self._requests = dict()


class IPCClientService(IPCService, metaclass=ABCMeta):

    def __init__(self,
                 read_conn: Connection,
                 write_conn: Connection,
                 proxy_object: object,
                 serializer: Optional[IPCMessageSerializer] = None,
                 ) -> None:

        super().__init__(read_conn, write_conn, serializer=serializer)
        self.proxy_object = proxy_object

        self._cls_to_fn = {v: k for k, v
                           in self.METHOD_MAP.items()}
        self._functions = {k: getattr(proxy_object, k) for k
                           in self.METHOD_MAP.keys()}

    @abstractmethod
    def _build_error_msg(self,
                         request_id: bytes,
                         fn_name: str,
                         result: Any) -> object:
        pass

    def _respond(self,
                 request_id: bytes,
                 fn_name: str,
                 result: Any) -> None:

        if isinstance(result, (Exception, Failure)):
            msg = self._build_error_msg(request_id, fn_name, result)
        else:
            msg = self._build_msg(request_id, fn_name, result)

        self._write(msg)

    def _on_request(self, msg: object) -> None:

        fn_name = self._cls_to_fn[msg]
        fn_spec = self._get_method_spec(fn_name)
        request_id = getattr(msg, 'request_id')

        # positional arguments present in function def
        args = []

        if fn_spec[0]:
            for kwarg in fn_spec[0]:
                args.append(getattr(msg, kwarg))

        # keyword arguments present in function def
        kwargs = {}

        if fn_spec[1]:
            for kwarg in fn_spec[1]:
                kwargs[kwarg] = getattr(msg, kwarg)

        # execute the call
        fn = self._functions[fn_name]

        def done(result):
            if isinstance(result, Deferred):
                result.addBoth(lambda r: self._respond(request_id, fn_name, r))
            else:
                self._respond(request_id, fn_name, result)

        def call():
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:  # pylint: disable=broad-except
                result = exc
            done(result)

        self._execute(call)

    @abstractmethod
    def _execute(self, fn: Callable) -> Any:
        """ Execute a function in a chosen context """
