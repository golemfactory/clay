import logging
import uuid

import time
from autobahn.twisted import WebSocketServerProtocol
from autobahn.twisted.websocket import WrappingWebSocketServerFactory, WebSocketClientProtocol, \
    WrappingWebSocketClientFactory
from twisted.internet.interfaces import IListeningPort

from golem.core.simpleserializer import CBORSerializer
from golem.rpc.service import ServiceNameProxy, to_names_list, full_name

logger = logging.getLogger(__name__)


REALM = 'Golem'

PROTOCOL_VERSION = '0.1'

RPC_ERR_NOT_FOUND = 'Not found'

class WebSocketAddress(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.address = u'ws://{}:{}/{}'.format(host, port, REALM)

    def __str__(self):
        return str(self.address)

    def __unicode__(self):
        return self.address


class WebSocketConnectionInfo(object):
    def __init__(self, conn_info):
        self.conn_info = conn_info

        if isinstance(conn_info, IListeningPort):
            self.host = conn_info.getHost()
            self.port = self.host.port
            host = self.host.host
        else:
            self.host = conn_info.host
            self.port = conn_info.port
            host = self.host

        if host == '0.0.0.0':
            host = '127.0.0.1'
        elif host == '::0':
            host = '::1'

        self.ws_address = WebSocketAddress(host, self.port)

    def __str__(self):
        return str(self.ws_address)

    def __unicode__(self):
        return self.ws_address


class IKeyring(object):
    def encrypt(self, message, identifier):
        raise NotImplementedError()

    def decrypt(self, message, identifier):
        raise NotImplementedError()


class DummyKeyring(IKeyring):
    def encrypt(self, message, identifier):
        return message

    def decrypt(self, message, identifier):
        return message


class KeyringMixin(object):
    def encrypt(self, message, _):
        if self.keyring:
            return self.keyring.encrypt(message)
        return message

    def decrypt(self, message, _):
        if self.keyring:
            return self.keyring.decrypt(message)
        return message


class SerializerMixin(object):
    def serialize(self, message):
        return self.serializer.loads(message)

    def deserialize(self, message):
        return self.serializer.dumps(message)


class MessageParserMixin(KeyringMixin, SerializerMixin):
    def receive_message(self, message, session_id):
        msg = self.deserialize(self.decrypt(message, session_id))

        if msg.protocol_version != PROTOCOL_VERSION:
            raise ValueError("Invalid protocol version")
        if not msg.id:
            raise ValueError("Invalid message id")

    def prepare_message(self, message, session_id):
        return self.encrypt(self.serialize(message), session_id)


class SessionMixin(object):
    def add_session(self, session):
        self.sessions[session.peer] = session

    def remove_session(self, session):
        self.sessions.pop(session.peer, None)

    def has_session(self, session):
        return session.peer in self.sessions

    def get_session(self, host, port):
        for peer, session in self.sessions.iteritems():
            if session.host == host and session.port == port:
                return session
        return None


class MessageLedger(object, MessageParserMixin):

    def __init__(self):
        self.requests = {}
        self.session_requests = {}

    def add_request(self, message, session):
        entry = dict(
            reponded=False,
            response=None,
            message=message
        )

        session_key = (session.host, session.port)
        if session_key not in self.session_requests:
            self.session_requests[session_key] = {}

        self.requests[message.id] = entry
        self.session_requests[session_key][message.id] = entry

    def add_response(self, message):
        if message.request_id in self.requests:
            request_dict = self.requests[message.request_id]
            request_dict.update(dict(
                responded=True,
                response=message
            ))

    def get_response(self, message):
        message_id = message.id

        if message_id in self.requests:
            entry = self.session_requests[message_id]
            return entry['responded'], entry['response']

        return False, None

    def clear_request(self, message_or_id):
        if not isinstance(message_or_id, basestring):
            message_or_id = message_or_id.id

        entry = self.requests.pop(message_or_id, None)
        if entry:
            session = entry['session']
            session_key = (session.host, session.port)
            session[session_key].pop(message_or_id, None)


class WebSocketRPCServerFactory(WrappingWebSocketServerFactory, MessageLedger, SessionMixin):

    def __init__(self, serializer, keyring, *args, **kwargs):
        WrappingWebSocketServerFactory.__init__(self, *args, **kwargs)
        MessageLedger.__init__(self)

        self.serializer = serializer
        self.keyring = keyring
        self.sessions = dict()

    def buildProtocol(self, addr):
        proto = WebSocketRPCServerProtocol()
        proto.factory = self
        proto._proto = self._factory.buildProtocol(addr)
        proto._proto.transport = proto
        return proto


class WebSocketRPCClientFactory(WrappingWebSocketClientFactory, MessageLedger, SessionMixin):

    def __init__(self, serializer, keyring, *args, **kwargs):
        WrappingWebSocketClientFactory.__init__(self, *args, **kwargs)
        MessageLedger.__init__(self)

        self.serializer = serializer
        self.keyring = keyring
        self.sessions = dict()

    def buildProtocol(self, addr):
        proto = WebSocketRPCClientProtocol()
        proto.factory = self
        proto._proto = self._factory.buildProtocol(addr)
        proto._proto.transport = proto
        return proto


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


class WebSocketRPCProtocol(object):

    def onOpen(self):
        self.factory.add_session(self)

    def connectionLost(self, reason):
        self.factory.remove_session(self)

    def onMessage(self, payload, is_binary):
        try:
            message = self.factory.receive_message(payload)
        except:
            message = None

        if isinstance(message, RPCRequestMessage):
            result, errors = self.perform_request(message)
            response = RPCResponseMessage(request_id=message.id,
                                          method=message.method,
                                          result=result,
                                          errors=errors)
            self.send_message(response)
        elif isinstance(message, RPCResponseMessage):
            self.factory.add_response(message, self)
        else:
            logger.error("RPC: received invalid message")

    def get_sessions(self):
        return self.factory.sessions

    def send_message(self, message):
        prepared = self.factory.prepare_message(message)
        self.sendMessage(prepared)

    def get_response(self, message):
        return self.factory.get_response(message)

    def perform_request(self):
        pass


class WebSocketRPCServerProtocol(WebSocketServerProtocol, WebSocketRPCProtocol):
    pass


class WebSocketRPCClientProtocol(WebSocketClientProtocol, WebSocketRPCProtocol):
    pass


class WebSocketRPCClient(WebSocketRPCClientFactory):

    def __init__(self, host, port, serializer=None, keyring=None):
        self.host = host
        self.port = port
        self.serializer = serializer or CBORSerializer
        self.keyring = keyring
        self.ws_connect_info = None
        self.factory = WebSocketRPCClientFactory(self.serializer, self.keyring)

    def connect(self):
        from twisted.internet import reactor

        connect_info = reactor.connectTCP(self.host, self.port, self.factory)
        self.ws_connect_info = WebSocketConnectionInfo(connect_info)

        logger.info("WebSocket RPC client connected to {}:{}"
                    .format(self.host, self.port))


class WebSocketRPCServer(WebSocketRPCClientFactory):

    def __init__(self, port=0, serializer=None, keyring=None):
        self.serializer = serializer or CBORSerializer
        self.keyring = keyring
        self.port = port
        self.ws_listen_info = None
        self.factory = WebSocketRPCServerFactory(self.serializer, self.keyring)

    def listen(self):
        from twisted.internet import reactor

        listen_info = reactor.listenTCP(self.port, self.factory)
        self.ws_listen_info = WebSocketConnectionInfo(listen_info)

        logger.info("WebSocket RPC server listening on {}"
                    .format(self.ws_listen_info))


class WebSocketRPCServiceInfo(object):

    def __init__(self, service, ws_address):
        self.full_service_name = full_name(service)
        self.method_names = to_names_list(service)
        self.ws_address = ws_address


class WebSocketRPCCall(object):

    def __init__(self, ws_rpc_client, timeout=10):
        self.ws_rpc_client = ws_rpc_client
        self.timeout = timeout

    def run(self, method_name, *args, **kwargs):
        rpc_request = RPCRequestMessage(method_name, *args, **kwargs)

        started = time.time()
        sleep = 0.01
        responded = False

        self.ws_rpc_client.send_message(rpc_request)

        while not responded:
            responded, response = self.ws_rpc_client.get_response(rpc_request)

            if responded:
                break
            elif time.time() - started > self.timeout:
                break
            else:
                time.sleep(sleep)

        if not responded:
            raise Exception("No response found")


class RPCClient(ServiceNameProxy):

    name_exceptions = ServiceNameProxy.name_exceptions + \
                      ['full_service_name', 'ws_rpc_client']

    def __init__(self, ws_rpc_client, full_service_name, method_names):
        self.full_service_name = full_service_name
        self.ws_rpc_client = ws_rpc_client
        ServiceNameProxy.__init__(self, method_names)

    def wrap(self, name, _):
        def wrapper(*args, **kwargs):
            return self.ws_rpc_client.call(name, *args, **kwargs)
        return wrapper
