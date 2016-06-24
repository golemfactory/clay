import uuid


PROTOCOL_VERSION = '0.1'


class RPCMessage(object):
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.protocol_version = PROTOCOL_VERSION


class RPCRequestMessage(RPCMessage):
    def __init__(self, method, *args, **kwargs):
        super(RPCRequestMessage, self).__init__()
        self.method = method
        self.args = args
        self.kwargs = kwargs


class RPCResponseMessage(RPCMessage):
    def __init__(self, request_id, method, result, errors, *args, **kwargs):
        super(RPCResponseMessage, self).__init__()
        self.request_id = request_id
        self.method = method
        self.result = result
        self.errors = errors
