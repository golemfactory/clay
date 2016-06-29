from twisted.internet.defer import inlineCallbacks, returnValue

from golem.rpc.exceptions import RPCSessionException
from golem.rpc.messages import RPCBatchCall, RPCBatchRequestMessage, RPCRequestMessage


class ServiceHelper(object):

    @staticmethod
    def to_dict(service):
        methods = {}

        for method in dir(service):
            attr = getattr(service, method)
            if ServiceHelper.is_accessible(method, attr):
                methods[method] = attr

        return methods

    @staticmethod
    def to_list(service):
        methods = []

        for method in dir(service):
            attr = getattr(service, method)
            if ServiceHelper.is_accessible(method, attr):
                methods.append(method)

        return methods

    @staticmethod
    def is_accessible(name, attr=None):
        if attr and not callable(attr):
            return False
        return not name.startswith('_')


class ServiceMethods(object):

    def __init__(self, service):
        if service:
            self.methods = ServiceHelper.to_dict(service)
        else:
            self.methods = {}


class ServiceProxy(ServiceMethods):

    _name_exceptions = ['service', 'methods', 'wrap',
                        'start_batch', 'call_batch']

    def __init__(self, service):
        ServiceMethods.__init__(self, service)

        for name, method in self.methods.iteritems():
            self.methods[name] = self.wrap(name, method)

    def __getattribute__(self, name, exceptions=None):
        exceptions = exceptions or ServiceProxy._name_exceptions

        if name.startswith('_') or name in exceptions:
            return object.__getattribute__(self, name)

        elif hasattr(self, 'methods'):
            return self.methods.get(name, None)

        return None

    def wrap(self, name, method):
        raise NotImplementedError()

    def start_batch(self):
        pass

    def call_batch(self, batch):
        pass


class ServiceMethodNamesProxy(ServiceProxy):

    def __init__(self, method_names):
        ServiceMethods.__init__(self, None)

        for name in method_names:
            self.methods[name] = self.wrap(name, None)

    def wrap(self, name, method):
        raise NotImplementedError()


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
        self.method_names = ServiceHelper.to_list(service)
        self.rpc_address = rpc_address


class RPCProxyService(object):

    def __init__(self, service):
        self.service_methods = ServiceMethods(service)

    def supports(self, method_name):
        return method_name in self.service_methods.methods

    def call(self, method_name, *args, **kwargs):
        method = self.service_methods.methods[method_name]
        return method(*args, **kwargs)


class RPCProxyClient(ServiceMethodNamesProxy):

    def __init__(self, rpc, method_names):
        self.rpc = rpc
        ServiceMethodNamesProxy.__init__(self, method_names)

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


class RPC(object):

    def __init__(self, factory, rpc_address, timeout=None):
        from twisted.internet import reactor

        self.reactor = reactor
        self.factory = factory
        self.timeout = timeout or 10

        self.rpc_address = rpc_address
        self.host = rpc_address.host
        self.port = rpc_address.port

    @inlineCallbacks
    def call(self, callee, is_batch, *args, **kwargs):
        session = self.get_session()

        if is_batch:
            rpc_request = RPCBatchRequestMessage(requests=callee)
        else:
            rpc_request = RPCRequestMessage(callee, args, kwargs)

        session.send_message(rpc_request)
        deferred, entry = session.get_response(rpc_request)
        response = yield deferred

        returnValue(response.result)

    def get_session(self):
        session = self.factory.get_session(self.host, self.port)
        if session:
            return session

        raise RPCSessionException("RPC: no session established with {}"
                                  .format(self.rpc_address))
