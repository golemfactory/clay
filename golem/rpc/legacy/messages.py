import uuid


PROTOCOL_VERSION = '0.1'


class RPCMessage(object):

    def __init__(self):
        self.id = str(uuid.uuid4())
        self.protocol_version = PROTOCOL_VERSION


class RPCRequestMessage(RPCMessage):

    def __init__(self, method, args, kwargs):
        super(RPCRequestMessage, self).__init__()
        self.method = method
        self.args = args
        self.kwargs = kwargs


class RPCBatchRequestMessage(RPCMessage):

    def __init__(self, requests):
        super(RPCBatchRequestMessage, self).__init__()
        self.requests = requests


class RPCResponseMessage(RPCMessage):

    def __init__(self, request_id, result, errors, *args, **kwargs):
        super(RPCResponseMessage, self).__init__()
        self.request_id = request_id
        self.result = result
        self.errors = errors


class RPCBatchCallEntry(object):

    def __init__(self, method, rpc_batch_call):
        self.method = method
        self.rpc_batch_call = rpc_batch_call

    def add(self, *args, **kwargs):
        message = RPCRequestMessage(self.method, args, kwargs)
        self.rpc_batch_call.calls.append(message)
        return self.rpc_batch_call

    def __call__(self, *args, **kwargs):
        return self.add(*args, **kwargs)


class RPCBatchCall(object):

    _name_exceptions = ['call', 'calls', 'rpc_client']

    def __init__(self, rpc_client):
        self.rpc_client = rpc_client
        self.calls = []

    def __getattribute__(self, name, exceptions=None):
        if name.startswith('_') or name in RPCBatchCall._name_exceptions:
            return object.__getattribute__(self, name)
        return RPCBatchCallEntry(name, self)

    def call(self):
        return self.rpc_client.call_batch(self)
