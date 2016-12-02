import collections

from golem.rpc.legacy.messages import RPCBatchCall, RPCBatchRequestMessage, RPCRequestMessage
from twisted.internet import task
from twisted.internet.defer import inlineCallbacks, returnValue, Deferred

CONNECTION_RETRY_TIMEOUT = 0.1  # s
CONNECTION_TIMEOUT = 3  # s


class ServiceHelper(object):

    @staticmethod
    def to_dict(service):
        methods = dict()

        for method in dir(service):
            attr = getattr(service, method)
            if ServiceHelper.is_accessible(method, attr):
                methods[method] = attr

        return methods

    @staticmethod
    def to_set(service):
        methods = set()

        for method in dir(service):
            attr = getattr(service, method)
            if ServiceHelper.is_accessible(method, attr):
                methods.add(method)

        return methods

    @staticmethod
    def is_accessible(name, attr=None):
        if attr and not callable(attr):
            return False
        return not name.startswith('_')


class ServiceMethods(object):

    def __init__(self, service):
        self.methods = ServiceHelper.to_dict(service)

    @staticmethod
    def names(mixed):
        if isinstance(mixed, ServiceMethods):
            return mixed.methods.keys()
        elif isinstance(mixed, dict):
            return mixed.keys()
        elif isinstance(mixed, collections.Iterable):
            return mixed
        return ServiceHelper.to_set(mixed)


class RPCAddress(object):

    def __init__(self, host, port, protocol=None):
        self.protocol = protocol or 'tcp'
        self.host = host
        self.port = port
        self.address = u'{}://{}:{}'.format(self.protocol,
                                            self.host, self.port)

    def __str__(self):
        return str(self.address)

    def __unicode__(self):
        return self.address


class RPCServiceInfo(object):

    def __init__(self, service, rpc_address):
        self.method_names = ServiceHelper.to_set(service)
        self.rpc_address = rpc_address


class RPCProxyService(object):

    def __init__(self, service):
        self.service_methods = ServiceMethods(service)

    def supports(self, method_name):
        return method_name in self.service_methods.methods

    def call(self, method_name, *args, **kwargs):
        method = self.service_methods.methods[method_name]
        return method(*args, **kwargs)


class RPCProxyClient(object):

    _name_exceptions = {'methods', 'wrap', 'start_batch', 'call_batch'}

    def __init__(self, rpc, methods):
        self.rpc = rpc
        self.methods = dict()

        for name in ServiceMethods.names(methods):
            self.methods[name] = self.wrap(name, None)

    def __getattribute__(self, name):
        if name.startswith('_') or name in self._name_exceptions:
            return object.__getattribute__(self, name)
        elif hasattr(self, 'methods'):
            return self.methods.get(name)

    def start_batch(self):
        return RPCBatchCall(self)

    def call_batch(self, batch):
        rpc = object.__getattribute__(self, 'rpc')
        return rpc.call(batch.calls, True)

    def wrap(self, name, _):
        rpc = object.__getattribute__(self, 'rpc')

        def wrapper(*args, **kwargs):
            return rpc.call(name, False, *args, **kwargs)
        return wrapper


class RPCSimpleClient(RPCProxyClient):

    class MethodCache(object):
        def __init__(self, client):
            self.cache = dict()
            self.client = client

        def get(self, key, _=None):
            if key not in self.cache:
                self.cache[key] = self.client.wrap(key, None)
            return self.cache[key]

    def __init__(self, rpc):
        super(RPCSimpleClient, self).__init__(rpc, None)
        self.methods = RPCSimpleClient.MethodCache(self)


class RPC(object):

    def __init__(self, factory, rpc_address,
                 conn_timeout=CONNECTION_TIMEOUT,
                 retry_timeout=CONNECTION_RETRY_TIMEOUT):

        from twisted.internet import reactor

        self.reactor = reactor
        self.factory = factory

        self.rpc_address = rpc_address
        self.host = rpc_address.host
        self.port = rpc_address.port

        self.retry_timeout = retry_timeout
        self.conn_timeout = conn_timeout

    @inlineCallbacks
    def call(self, callee, is_batch, *args, **kwargs):
        session = yield self.get_session()

        if is_batch:
            rpc_request = RPCBatchRequestMessage(requests=callee)
        else:
            rpc_request = RPCRequestMessage(callee, args, kwargs)

        response = yield session.send_message(rpc_request)
        # TODO: handle response errors
        # if response.errors:
        #     raise RPCServiceError(response.errors)
        returnValue(response.result)

    @inlineCallbacks
    def get_session(self):
        session = self.factory.get_session(self.host, self.port)
        if not session:
            session = yield self._wait_for_session(self.host, self.port)
        returnValue(session)

    def _wait_for_session(self, host, port):
        deferred = Deferred()

        def on_success(result):
            if result:
                deferred.callback(result)
            else:
                retry()

        def retry(*_):
            conn_deferred = task.deferLater(self.reactor, self.retry_timeout,
                                            self.factory.get_session, host, port,
                                            timeout=self.conn_timeout)
            conn_deferred.addCallbacks(on_success, retry)

        retry()
        return deferred
