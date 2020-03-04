import abc
import logging
import typing


import transitions
from twisted.internet.protocol import Factory, Protocol, connectionDone

from .tcpnetwork_helpers import TCPConnectInfo, TCPListenInfo, TCPListeningInfo


logger = logging.getLogger(__name__)


class ExtendedMachine(transitions.Machine):
    def add_transition_callback(  # pylint: disable=too-many-arguments
            self,
            trigger: str,
            source,
            dest: str,
            callback_trigger: str,  # 'before', 'after' or 'prepare'
            callback_func,
    ):
        for transition in self.get_transitions(trigger, source, dest):
            transition.add_callback(
                trigger=callback_trigger,
                func=callback_func,
            )

    def copy_transitions(  # pylint: disable=too-many-arguments
            self,
            from_trigger: str,
            from_source: str,
            from_dest: str,
            to_trigger: str,
            to_source: str,
            to_dest: str,
    ):
        for transition in self.get_transitions(
                from_trigger,
                from_source,
                from_dest,
        ):
            self.add_transition(
                trigger=to_trigger,
                source=to_source,
                dest=to_dest,
                before=transition.before,
                after=transition.after,
                prepare=transition.prepare,
            )
            # conditions are ignored, implement if needed

    def move_transitions(  # pylint: disable=too-many-arguments
            self,
            from_trigger: str,
            from_source: str,
            from_dest: str,
            to_trigger: str,
            to_source: str,
            to_dest: str,
    ):
        self.copy_transitions(
            from_trigger,
            from_source,
            from_dest,
            to_trigger,
            to_source,
            to_dest,
        )
        self.remove_transition(from_trigger, from_source, from_dest)


class Network(abc.ABC):
    @abc.abstractmethod
    def connect(self, connect_info: TCPConnectInfo) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def listen(self, listen_info: TCPListenInfo) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def stop_listening(self, listening_info: TCPListeningInfo):
        raise NotImplementedError


class SessionFactory(object):
    CONN_TYPE: typing.Optional[int] = None

    def __init__(self, session_class):
        self.session_class = session_class

    @classmethod
    def from_factory(cls, factory: 'SessionFactory') -> 'SessionFactory':
        return cls(session_class=factory.session_class)

    def get_session(self, conn) -> 'Session':
        session = self.session_class(conn)
        session.conn_type = self.CONN_TYPE
        return session


class ProtocolFactory(Factory):
    SESSION_WRAPPER: typing.Optional[typing.Type['SessionFactory']] = None

    def __init__(self, protocol_class, server=None, session_factory=None):
        self.protocol_class = protocol_class
        self.server = server
        if self.SESSION_WRAPPER is not None:
            session_factory = self.SESSION_WRAPPER.from_factory(session_factory)
        self.session_factory = session_factory

    @classmethod
    def from_factory(cls, factory: 'ProtocolFactory') -> 'ProtocolFactory':
        return cls(
            protocol_class=factory.protocol_class,
            server=factory.server,
            session_factory=factory.session_factory,
        )

    def buildProtocol(self, addr):
        return self.protocol_class(self.session_factory, server=self.server)


class SessionProtocol(Protocol):
    def __init__(self, session_factory, **_kwargs):
        """Connection-oriented basic protocol for twisted"""
        self.session_factory = session_factory
        self.session: typing.Optional[Session] = None
        self.machine = ExtendedMachine(
            self,
            states=[
                'initial',
                'connected',
                'disconnected',
            ],
            initial='initial',
            auto_transitions=False,
        )
        self.machine.add_transition(
            'connectionMadeTransition',
            'initial',
            'connected',
            after=self.create_session or True,  # always True
        )
        self.machine.add_transition(
            'connectionLostTransition',
            '*',
            'disconnected',
            after=lambda reason: (
                delattr(self, 'session') or True  # always True
            ),
        )

    def connectionMade(self):
        super().connectionMade()
        # map twisted Protocol event into transition
        self.connectionMadeTransition()  # pylint: disable=no-member

    def connectionLost(self, reason=connectionDone):
        super().connectionLost(reason=reason)
        # map twisted Protocol event into transition
        self.connectionLostTransition(reason=reason)  # noqa pylint: disable=no-member

    def create_session(self) -> bool:
        """Called when new connection is successfully opened"""

        # If the underlying transport is TCP, enable TCP keepalive.
        # Otherwise, the setTcpKeepAlive method will not be present
        # in the 'transport' object and an AttributeError will be raised
        try:
            self.transport.setTcpKeepAlive(1)
        except AttributeError:
            pass

        self.session = self.session_factory.get_session(self)
        return True


class Session(object, metaclass=abc.ABCMeta):
    CONN_TYPE_CLIENT = 1
    CONN_TYPE_SERVER = 2

    def __init__(self):
        self.conn_type = None

    @abc.abstractmethod
    def dropped(self):
        raise NotImplementedError

    @abc.abstractmethod
    def interpret(self, msg):
        raise NotImplementedError

    @abc.abstractmethod
    def disconnect(self, reason):
        raise NotImplementedError


class IncomingSessionFactory(SessionFactory):
    CONN_TYPE = Session.CONN_TYPE_SERVER


class OutgoingSessionFactory(SessionFactory):
    CONN_TYPE = Session.CONN_TYPE_CLIENT


class IncomingProtocolFactory(ProtocolFactory):
    SESSION_WRAPPER = IncomingSessionFactory


class OutgoingProtocolFactory(ProtocolFactory):
    SESSION_WRAPPER = OutgoingSessionFactory
