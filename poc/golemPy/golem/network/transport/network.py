import abc
from twisted.internet.protocol import Factory, Protocol


class Network(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def connect(self, connect_info, **kwargs):
        return

    @abc.abstractmethod
    def listen(self, listen_info, **kwargs):
        return

    @abc.abstractmethod
    def stop_listening(self, listening_info, **kwargs):
        return


class SessionFactory(Factory):
    def __init__(self, session_class):
        self.session_class = session_class

    def get_session(self, conn):
        return self.session_class(conn)


class ProtocolFactory(Factory):
    def __init__(self, protocol_class, server=None, session_factory=None):
        self.protocol_class = protocol_class
        self.server = server
        self.session_factory = session_factory

    def buildProtocol(self, addr):
        protocol = self.protocol_class(self.server)
        protocol.set_session_factory(self.session_factory)
        return protocol


class SessionProtocol(Protocol):
    def __init__(self):
        self.session_factory = None
        self.session = None

    def set_session_factory(self, session_factory):
        self.session_factory = session_factory

    def connectionMade(self):
        Protocol.connectionMade(self)
        self.session = self.session_factory.get_session(self)


class Session(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def __init__(self, conn):
        return

    @abc.abstractmethod
    def dropped(self):
        return

    @abc.abstractmethod
    def interpret(self, msg):
        return

    @abc.abstractmethod
    def disconnect(self, reason):
        return
