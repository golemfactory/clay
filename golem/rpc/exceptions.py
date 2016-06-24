class RPCException(Exception):
    pass


class RPCTimeout(RPCException):
    pass


class RPCResponseError(RPCException):
    pass


class RPCNotConnected(RPCException):
    pass
