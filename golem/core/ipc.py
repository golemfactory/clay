import functools
import uuid
from abc import abstractmethod, ABCMeta
from multiprocessing import Process
from multiprocessing.connection import Connection
from typing import Optional, List, Any, Dict, Set, Callable

from twisted.internet.defer import Deferred
from twisted.python.failure import Failure

from golem.core.service import IService, ThreadedService
from golem.core.simpleserializer import CBORSerializer


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
        pass

    @abstractmethod
    def _get_spawn_arguments(self) -> List[Any]:
        pass


class IPCService(ThreadedService):

    POLL_TIMEOUT = 0.5  # s

    def __init__(self,
                 read_conn: Connection,
                 write_conn: Connection) -> None:

        super().__init__()

        self._read_conn = read_conn
        self._write_conn = write_conn

    @abstractmethod
    def send(self, key: str, *args, **kwargs) -> Optional[Deferred]:
        pass

    @abstractmethod
    def receive(self) -> None:
        pass

    @abstractmethod
    def _on_close(self, error: Optional[Exception] = None) -> None:
        pass

    @abstractmethod
    def _on_error(self, error: Optional[Exception] = None) -> None:
        pass

    def _read(self) -> Optional[bytes]:

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
            return CBORSerializer.loads(data)
        except Exception as exc:  # pylint: disable=broad-except
            self._on_error(exc)
            return None

    def _write(self, data: Any) -> bool:

        # Serialize data
        try:
            serialized = CBORSerializer.dumps(data)
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

    METHODS: Set[str] = set()  # collection of methods to proxify

    def __init__(self, read_conn, write_conn):
        super().__init__(read_conn, write_conn)

        self._requests: Dict[str, Deferred] = dict()  # deferred requests
        self._functions: Dict[str, functools.partial] = dict()  # proxy funcs

    def __getattribute__(self, item: str) -> Any:
        """
        Create and return a proxy function for any method in METHODS;
        return all other properties as-is.
        """

        if item != 'METHODS' and item in self.METHODS:
            if item not in self._functions:
                self._functions[item] = functools.partial(self.send, item)
            return self._functions[item]

        return super().__getattribute__(item)

    @staticmethod
    def new_request_id() -> str:
        return str(uuid.uuid4())

    def send(self, key: str, *args, **kwargs) -> Optional[Deferred]:

        request_id = self.new_request_id()
        request = request_id, (key, args, kwargs)
        deferred = Deferred()

        if super()._write(request):
            self._requests[request_id] = deferred
        else:
            error = RuntimeError('Unable to send a request: {}({}, {})'
                                 .format(key, args, kwargs))
            deferred.errback(error)

        return deferred

    def receive(self) -> None:

        data: Optional[bytes] = super()._read()
        if not isinstance(data, (list, tuple)):
            return

        try:
            request_id, response = data
        except TypeError as exc:
            self._on_error(exc)
            return

        if request_id not in self._requests:
            error = RuntimeError('Unknown request id: {}'.format(request_id))
            self._on_error(error)
            return

        deferred = self._requests.pop(request_id)

        if isinstance(response, (Exception, Failure)):
            fn = deferred.errback
        else:
            fn = deferred.callback

        fn(response)

    def _on_close(self, error: Optional[Exception] = None) -> None:
        super()._on_close(error)

        self._requests = dict()


class IPCClientService(IPCService, metaclass=ABCMeta):

    def __init__(self,
                 read_conn: Connection,
                 write_conn: Connection,
                 proxy_object: object) -> None:

        super().__init__(read_conn, write_conn)
        self.proxy_object = proxy_object

    def send(self,
             key: str,
             *args,
             **_) -> Optional[Deferred]:

        response = key, args[0]
        super()._write(response)
        return None

    def receive(self) -> None:

        data = super()._read()
        if not isinstance(data, (list, tuple)):
            return

        try:
            request_id, (fn_name, args, kwargs) = data
        except TypeError as exc:
            self._on_error(exc)
            return

        fn = getattr(self.proxy_object, fn_name, None)

        def done(result):
            if isinstance(result, Deferred):
                result.addBoth(lambda r: self.send(request_id, r))
            else:
                self.send(request_id, result)

        def call():
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:  # pylint: disable=broad-except
                result = exc
            done(result)

        self._execute(call)

    @abstractmethod
    def _execute(self, fn: Callable) -> Any:
        """ Executes a function in a chosen context """
