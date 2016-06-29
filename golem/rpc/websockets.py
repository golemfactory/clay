import logging
import sys

from autobahn.twisted import WebSocketServerProtocol
from autobahn.twisted.websocket import WebSocketClientProtocol, \
    WebSocketServerFactory, WebSocketClientFactory
from twisted.internet.defer import Deferred
from twisted.internet.tcp import Port

from golem.core.simpleserializer import DILLSerializer
from golem.rpc.exceptions import RPCNotConnected, RPCServiceError, RPCProtocolError, \
    RPCMessageError
from golem.rpc.messages import RPCRequestMessage, RPCResponseMessage, PROTOCOL_VERSION, RPCBatchRequestMessage
from golem.rpc.service import RPCProxyService, RPCProxyClient, RPCAddress, RPC, RPCServiceInfo


logger = logging.getLogger(__name__)


class WebSocketAddress(RPCAddress):

    def __init__(self, host, port):
        super(WebSocketAddress, self).__init__(host, port,
                                               protocol=u'ws')

    @staticmethod
    def from_connector(connector):

        if isinstance(connector, Port):
            conn_host = connector.getHost()
            host = conn_host.host
            port = conn_host.port
        else:
            host = connector.host
            port = connector.port

        if host == '0.0.0.0':
            host = '127.0.0.1'
        elif host == '::0':
            host = '::1'

        return WebSocketAddress(host, port)


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
        if message is None:
            return None
        elif isinstance(message, basestring):
            return self.serializer.loads(message)
        return self.serializer.loads(str(message))


class MessageParserMixin(KeyringMixin, SerializerMixin):

    def receive_message(self, message, session_id):
        msg = self.deserialize(self.decrypt(message, session_id))

        if msg.protocol_version != PROTOCOL_VERSION:
            raise RPCProtocolError("Invalid protocol version")
        elif not msg.id:
            raise RPCMessageError("Invalid message id")

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

        except Exception as exc:
            logger.error("RPC: error parsing message {}"
                         .format(exc))
            print("RPC: error parsing message {}"
                         .format(exc))
            import traceback
            traceback.print_exc()

            message = None

        if isinstance(message, RPCRequestMessage):
            self.perform_requests(message)

        elif isinstance(message, RPCBatchRequestMessage):
            self.perform_requests(message, batch=True)

        elif isinstance(message, RPCResponseMessage):
            self.factory.add_response(message)

        elif message:
            logger.error("RPC: received unknown message {}"
                         .format(message))

    def perform_requests(self, message, batch=False):

        results = None
        errors = None

        try:
            if batch:
                results = list()
                for request in message.requests:
                    result = self.factory.perform_request(request.method,
                                                          request.args,
                                                          request.kwargs)
                    results.append(result)
            else:
                results = self.factory.perform_request(message.method,
                                                       message.args,
                                                       message.kwargs)
        except Exception as exc:
            errors = exc.message

            import traceback
            traceback.print_exc()

        response = RPCResponseMessage(request_id=message.id,
                                      result=results,
                                      errors=errors)

        self.send_message(response, add_request=False)

    def send_message(self, message, add_request=True):
        try:
            if add_request:
                self.factory.add_request(message, self)
            prepared = self.factory.prepare_message(message, id(self))

        except Exception as exc:

            if add_request and message:
                self.factory.remove_request(message)

            logger.error("RPC: error sending message: {}"
                         .format(exc))
        else:
            self.sendMessage(prepared, isBinary=True)

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
            raise RPCNotConnected("Not connected")

        self.services.append(RPCProxyService(service))
        ws_address = WebSocketAddress(self.local_host, self.local_port)

        return RPCServiceInfo(service, ws_address)

    def build_client(self, service_info, timeout=None):
        rpc = RPC(self, service_info.rpc_address, timeout=timeout)

        return RPCProxyClient(rpc, service_info.method_names)

    def perform_request(self, method, args, kwargs):
        for server in self.services:
            if server.supports(method):
                return server.call(method, *args, **kwargs)

        raise RPCServiceError("Local service call not supported: {}"
                              .format(method))


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

        listener = reactor.listenTCP(self.listen_port, self)
        ws_conn_info = WebSocketAddress.from_connector(listener)

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
        self.status.addCallback(self.client_connected)

    def connect(self):
        from twisted.internet import reactor

        self.connector = reactor.connectTCP(self.remote_host, self.remote_port, self)
        ws_address = WebSocketAddress(self.remote_host, self.remote_port)

        logger.info("WebSocket RPC client connecting to {}"
                    .format(ws_address))
        return self.status

    def add_session(self, session):
        WebSocketRPCFactory.add_session(self, session)
        self.status.callback(session)

    # def clientConnectionLost(self, connector, reason):
    #     self.remove_session()

    def clientConnectionFailed(self, connector, reason):
        self.status.errback(reason)

    def client_connected(self, *args):
        addr = self.connector.transport.socket.getsockname()
        self.local_host = addr[0]
        self.local_port = addr[1]
