import logging
import traceback

from autobahn.twisted import WebSocketServerProtocol
from autobahn.twisted.websocket import WebSocketClientProtocol, \
    WebSocketServerFactory, WebSocketClientFactory
from twisted.internet.defer import Deferred, inlineCallbacks, returnValue
from twisted.internet.tcp import Port

from golem.core.simpleserializer import DILLSerializer
from golem.rpc.messages import RPCRequestMessage, RPCResponseMessage, PROTOCOL_VERSION
from golem.rpc.service import ServiceNameProxy, to_names_list, to_dict

logger = logging.getLogger(__name__)


class WebSocketAddress(object):

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.address = u'ws://{}:{}'.format(host, port)

    def __str__(self):
        return str(self.address)

    def __unicode__(self):
        return self.address


class WebSocketConnectionInfo(WebSocketAddress):

    def __init__(self, conn_info):

        if isinstance(conn_info, Port):
            conn_host = conn_info.getHost()
            host = conn_host.host
            port = conn_host.port
        else:
            host = conn_info.host
            port = conn_info.port

        if host == '0.0.0.0':
            host = '127.0.0.1'
        elif host == '::0':
            host = '::1'

        super(WebSocketConnectionInfo, self).__init__(host, port)


class IKeyring(object):

    def encrypt(self, message, identifier):
        raise NotImplementedError()

    def decrypt(self, message, identifier):
        raise NotImplementedError()


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
        if message is None:
            return None
        return self.serializer.dumps(message)

    def deserialize(self, message):
        if isinstance(message, basestring):
            return self.serializer.loads(message)
        elif message is None:
            return None
        return self.serializer.loads(str(message))


class MessageParserMixin(KeyringMixin, SerializerMixin):

    def receive_message(self, message, session_id):
        msg = self.deserialize(self.decrypt(message, session_id))

        if msg.protocol_version != PROTOCOL_VERSION:
            raise ValueError("Invalid protocol version")
        elif not msg.id:
            raise ValueError("Invalid message id")

        return msg

    def prepare_message(self, message, session_id):
        return self.encrypt(self.serialize(message), session_id)


class SessionManager(object):

    def __init__(self):
        self.sessions = {}

    def add_session(self, session):
        self.sessions[session.peer] = session

    def remove_session(self, session):
        self.sessions.pop(session.peer, None)

    def has_session(self, session):
        return session.peer in self.sessions

    def get_session(self, host, port):
        for _, session in self.sessions.iteritems():
            peer = session.transport.getPeer()
            if peer.host == host and peer.port == port:
                return session
        return None


class MessageLedger(MessageParserMixin):

    def __init__(self):
        self.requests = {}
        self.session_requests = {}

    def add_request(self, message, session):
        logger.debug("add request (ledger) {} {}".format(id(self), message.id))

        entry = dict(
            responded=False,
            response=None,
            message=message,
            session=session,
            deferred=Deferred()
        )

        self.requests[message.id] = entry

        session_key = self._get_session_key(session)
        if session_key not in self.session_requests:
            self.session_requests[session_key] = {}
        self.session_requests[session_key][message.id] = entry

    def add_response(self, message):
        logger.debug("add response (ledger) {} {} for {}".format(id(self), message.id, message.request_id))

        if message.request_id in self.requests:
            request_dict = self.requests[message.request_id]
            request_dict.update(dict(
                responded=True,
                response=message
            ))

            deferred = request_dict['deferred']
            deferred.callback(message)

    def get_response(self, message):
        message_id = message.id

        if message_id in self.requests:
            entry = self.requests[message_id]
            return entry['deferred'], entry

        return None, None

    def clear_request(self, message_or_id):
        if not isinstance(message_or_id, basestring):
            message_or_id = message_or_id.id

        entry = self.requests.pop(message_or_id, None)
        if entry:
            session_key = self._get_session_key(entry['session'])
            self.session_requests[session_key].pop(message_or_id, None)

    @staticmethod
    def get_session_addr(session):
        peer = session.transport.getPeer()
        return peer.host, peer.port

    @classmethod
    def _get_session_key(cls, session):
        return cls.get_session_addr(session)


class WebSocketRPCProtocol(object):

    def onOpen(self):
        self.factory.add_session(self)

    def onClose(self, wasClean, code, reason):
        self.factory.remove_session(self)

    def onMessage(self, payload, isBinary):
        try:
            message = self.factory.receive_message(payload, id(self))
        except:
            message = None

        if isinstance(message, RPCRequestMessage):
            result, errors = None, None
            try:
                result = self.factory.perform_request(message)
            except Exception as exc:
                errors = exc.message

            response = RPCResponseMessage(request_id=message.id,
                                          method=message.method,
                                          result=result,
                                          errors=errors)

            self.send_message(response, add_request=False)

        elif isinstance(message, RPCResponseMessage):
            self.factory.add_response(message)
        else:
            logger.error("RPC: received invalid message")

    def send_message(self, message, add_request=True):
        try:
            if add_request:
                self.factory.add_request(message, self)

            prepared = self.factory.prepare_message(message, id(self))
            self.sendMessage(prepared, isBinary=True)
        except Exception as exc:
            logger.error("RPC: error sending message: {}"
                         .format(exc))
            traceback.print_exc()

    def get_response(self, message):
        return self.factory.get_response(message)

    def get_sessions(self):
        return self.factory.sessions


class WebSocketRPCServerProtocol(WebSocketRPCProtocol, WebSocketServerProtocol):
    pass


class WebSocketRPCClientProtocol(WebSocketRPCProtocol, WebSocketClientProtocol):
    pass


class WebSocketRPCFactory(MessageLedger, SessionManager):

    def __init__(self):
        MessageLedger.__init__(self)
        SessionManager.__init__(self)

        self.services = []
        self.local_host = None
        self.local_port = None

    def add_service(self, service):
        if not self.local_host:
            raise Exception("Not connected")

        rpc_proxy = RPCProxyService(service)
        self.services.append(rpc_proxy)

        return WebSocketRPCServiceInfo(service, WebSocketAddress(self.local_host, self.local_port))

    def build_client(self, service_info, timeout=None):
        rpc = RPC(self, service_info.ws_address, timeout=timeout)
        return RPCProxyClient(rpc, service_info.method_names)

    def perform_request(self, message):
        for server in self.services:
            if server.supports(message.method):
                return server.call(message.method,
                                   *message.args,
                                   **message.kwargs)

        raise Exception("Local service call not supported: {}"
                        .format(message.__dict__))


class WebSocketRPCServerFactory(WebSocketRPCFactory, WebSocketServerFactory):

    protocol = WebSocketRPCServerProtocol

    def __init__(self, port=0, serializer=None, keyring=None, *args, **kwargs):
        WebSocketServerFactory.__init__(self, *args, **kwargs)
        WebSocketRPCFactory.__init__(self)

        self.serializer = serializer or DILLSerializer
        self.keyring = keyring
        self.listen_port = port

    def listen(self):
        from twisted.internet import reactor

        listen_info = reactor.listenTCP(self.listen_port, self)
        ws_conn_info = WebSocketConnectionInfo(listen_info)

        self.local_host = ws_conn_info.host
        self.local_port = ws_conn_info.port

        logger.info("WebSocket RPC server listening on {}"
                    .format(ws_conn_info))


class WebSocketRPCClientFactory(WebSocketRPCFactory, WebSocketClientFactory):

    protocol = WebSocketRPCClientProtocol

    def __init__(self, remote_host, remote_port, serializer=None, keyring=None, *args, **kwargs):

        WebSocketClientFactory.__init__(self, *args, **kwargs)
        WebSocketRPCFactory.__init__(self)

        self.remote_host = remote_host
        self.remote_port = remote_port
        self.connector = None

        self.serializer = serializer or DILLSerializer
        self.keyring = keyring

        self.status = Deferred()
        self.status.addCallback(self.__connected)

    def connect(self):
        from twisted.internet import reactor
        self.connector = reactor.connectTCP(self.remote_host, self.remote_port, self)

        logger.info("WebSocket RPC client connecting to {}"
                    .format(WebSocketAddress(self.remote_host, self.remote_port)))
        return self.status

    def add_session(self, session):
        WebSocketRPCFactory.add_session(self, session)
        self.status.callback(session)

    # def clientConnectionLost(self, connector, reason):
    #     self.remove_session()

    def clientConnectionFailed(self, connector, reason):
        self.status.errback(reason)

    def __connected(self, *args):
        addr = self.connector.transport.socket.getsockname()
        self.local_host = addr[0]
        self.local_port = addr[1]


class WebSocketRPCServiceInfo(object):

    def __init__(self, service, ws_address):
        self.method_names = to_names_list(service)
        self.ws_address = ws_address


class RPC(object):

    def __init__(self, factory, ws_address, timeout=None):
        from twisted.internet import reactor

        self.reactor = reactor
        self.factory = factory
        self.host = ws_address.host
        self.port = ws_address.port
        self.timeout = timeout or 2

    @inlineCallbacks
    def call(self, method_name, *args, **kwargs):
        logger.debug("RPC call {}".format(method_name))

        session = self.factory.get_session(self.host, self.port)
        if not session:
            raise Exception("RPC: no session for {}:{} ({}) : {}"
                            .format(self.host, self.port,
                                    method_name, self.factory.sessions))

        rpc_request = RPCRequestMessage(method_name, args, kwargs)

        session.send_message(rpc_request)
        deferred, entry = session.get_response(rpc_request)

        response = yield deferred
        returnValue(response.result)


class RPCProxyService(object):

    def __init__(self, service):
        self.methods = to_dict(service)

    def supports(self, method_name):
        return method_name in self.methods

    def call(self, method_name, *args, **kwargs):
        return self.methods[method_name](*args, **kwargs)


class RPCProxyClient(ServiceNameProxy):

    name_exceptions = ServiceNameProxy.name_exceptions + ['rpc']

    def __init__(self, rpc, method_names):
        self.rpc = rpc
        ServiceNameProxy.__init__(self, method_names)

    def wrap(self, name, _):
        rpc = object.__getattribute__(self, 'rpc')

        def wrapper(*args, **kwargs):
            return rpc.call(name, *args, **kwargs)
        return wrapper
