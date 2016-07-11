class RPCException(Exception):
    pass


class RPCTimeout(RPCException):
    pass


class RPCProtocolError(RPCException):
    pass


class RPCMessageError(RPCException):
    pass


class RPCServiceError(RPCException):
    pass


class RPCNotConnected(RPCException):
    pass


class RPCSessionException(RPCException):
    pass
