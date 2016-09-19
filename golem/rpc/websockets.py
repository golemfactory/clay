import logging
import time
from collections import deque

import sys
from autobahn.twisted import WebSocketServerProtocol
from autobahn.twisted.websocket import WebSocketClientProtocol, \
    WebSocketServerFactory, WebSocketClientFactory
from twisted.internet import task
from twisted.internet.defer import Deferred
from twisted.internet.tcp import Port

from golem.core.simpleserializer import DILLSerializer
from golem.rpc.exceptions import RPCNotConnected, RPCServiceError, RPCProtocolError, \
    RPCMessageError
from golem.rpc.messages import RPCRequestMessage, RPCResponseMessage, PROTOCOL_VERSION, RPCBatchRequestMessage
from golem.rpc.service import RPCProxyService, RPCProxyClient, RPCAddress, RPC, RPCServiceInfo, RPCSimpleClient

logger = logging.getLogger(__name__)


RECONNECT_TIMEOUT = 0.5  # s
REQUEST_REMOVE_INTERVAL = 1  # s
REQUEST_REMOVE_TIMEOUT = 90  # s


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


class SessionAwareMixin(object):

    @staticmethod
    def get_session_addr(session):
        peer = session.transport.getPeer()
        return peer.host, peer.port


class SessionManager(SessionAwareMixin):

    def __init__(self):
        self.sessions = {}

    def add_session(self, session):
        addr = self.get_session_addr(session)
        self.sessions[addr] = session

    def remove_session(self, session):
        addr = self.get_session_addr(session)
        self.sessions.pop(addr, None)

    def has_session(self, session):
        addr = self.get_session_addr(session)
        return addr in self.sessions

    def get_session(self, host, port, timeout=None):
        for session_key, session in self.sessions.items():
            if session_key == (host, port):
                return session
        return None


class MessageLedger(MessageParserMixin, SessionAwareMixin):

    def __init__(self):
        self.requests = {}

    def add_request(self, message, session):
        session_key = self._get_session_key(session)
        deferred = Deferred()

        entry = dict(
            message=message,
            session_key=session_key,
            deferred=deferred,
            retried=0,
            created=time.time(),
        )

        self.requests[message.id] = entry
        return deferred

    def remove_request(self, message_or_id):
        if not isinstance(message_or_id, basestring):
            message_or_id = message_or_id.id

        return self.requests.pop(message_or_id, None)

    def add_response(self, message):
        entry = self.remove_request(message.request_id)

        if entry:
            deferred = entry['deferred']
            if not deferred.called:
                deferred.callback(message)

    def get_response(self, message):
        return self.requests.get(message.id, None)

    def _get_session_key(self, session):
        return self.get_session_addr(session)


class WebSocketRPCProtocol(object):

    def __init__(self):
        self._requests_task = task.LoopingCall(self._remove_old_requests)

    def onOpen(self):
        self.factory.add_session(self)
        if not self._requests_task.running:
            self._requests_task.start(REQUEST_REMOVE_INTERVAL)

    def onClose(self, was_clean, code, reason):
        self.factory.remove_session(self)
        if self._requests_task.running:
            self._requests_task.stop()

    def onMessage(self, payload, isBinary):

        try:
            message = self.factory.receive_message(payload, id(self))
        except Exception as exc:
            message = None
            logger.error("RPC: error parsing message {}"
                         .format(exc))

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
                results = deque()
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

        self.send_message(response, new_request=False)

    def send_message(self, message, new_request=True):
        deferred = None

        try:
            if new_request:
                deferred = self.factory.add_request(message, self)
            prepared = self.factory.prepare_message(message, id(self))
        except Exception as exc:

            if new_request and message:
                self.factory.remove_request(message)

            logger.error("RPC: error sending message: {}"
                         .format(exc))

            import traceback
            traceback.print_exc()

        else:
            self.sendMessage(prepared, isBinary=True)

        return deferred

    def retry_requests(self):
        for request in self.factory.requests.values():
            self.send_message(request['message'], new_request=False)

    def _remove_old_requests(self):
        now = time.time()
        for request in self.factory.requests.values():
            if now - request['created'] >= REQUEST_REMOVE_TIMEOUT:
                self.factory.remove_request(request['message'])


class WebSocketRPCServerProtocol(WebSocketRPCProtocol, WebSocketServerProtocol):
    def __init__(self):
        WebSocketServerProtocol.__init__(self)
        WebSocketRPCProtocol.__init__(self)


class WebSocketRPCClientProtocol(WebSocketRPCProtocol, WebSocketClientProtocol):
    def __init__(self):
        WebSocketClientProtocol.__init__(self)
        WebSocketRPCProtocol.__init__(self)


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
        rpc = RPC(self, service_info.rpc_address, conn_timeout=timeout)

        return RPCProxyClient(rpc, service_info.method_names)

    def perform_request(self, method, args, kwargs):
        for server in self.services:
            if server.supports(method):
                result = server.call(method, *args, **kwargs)
                # Prevent serialization of Deferred, which *will* cause problems on the receiving side,
                # as results of Deferred type in Deferred callbacks are not allowed
                if isinstance(result, Deferred):
                    return None
                return result

        raise RPCServiceError("Local service call not supported: {}"
                              .format(method))


class WebSocketRPCServerFactory(WebSocketRPCFactory, WebSocketServerFactory):

    protocol = WebSocketRPCServerProtocol

    def __init__(self, interface='', port=0, serializer=None, keyring=None, *args, **kwargs):
        WebSocketServerFactory.__init__(self, *args, **kwargs)
        WebSocketRPCFactory.__init__(self)

        self.serializer = serializer or DILLSerializer
        self.keyring = keyring
        self.listen_interface = interface
        self.listen_port = port

    def listen(self):
        from twisted.internet import reactor

        listener = reactor.listenTCP(self.listen_port, self,
                                     interface=self.listen_interface)
        ws_conn_info = WebSocketAddress.from_connector(listener)

        self.local_host = ws_conn_info.host
        self.local_port = ws_conn_info.port

        logger.info("WebSocket RPC server listening on {}"
                    .format(ws_conn_info))


class WebSocketRPCClientFactory(WebSocketRPCFactory, WebSocketClientFactory):

    protocol = WebSocketRPCClientProtocol

    def __init__(self, remote_host, remote_port, serializer=None, keyring=None,
                 on_disconnect=None, *args, **kwargs):

        from twisted.internet import reactor

        WebSocketClientFactory.__init__(self, *args, **kwargs)
        WebSocketRPCFactory.__init__(self)

        self.reactor = reactor
        self.connector = None

        self.remote_host = remote_host
        self.remote_port = remote_port
        self.remote_ws_address = WebSocketAddress(self.remote_host, self.remote_port)

        self.serializer = serializer or DILLSerializer
        self.keyring = keyring

        self.on_disconnect = on_disconnect
        self._reconnect_timeout = kwargs.pop('reconnect_timeout', RECONNECT_TIMEOUT)
        self._deferred = None

    def connect(self, timeout=None):

        self._deferred = Deferred()
        self._deferred.addCallback(self._client_connected)

        logger.info("WebSocket RPC: connecting to {}".format(self.remote_ws_address))

        self.connector = self.reactor.connectTCP(self.remote_host, self.remote_port,
                                                 self, timeout=timeout)
        return self._deferred

    def disconnect(self):
        if self.connector:
            self.connector.disconnect()

    def build_simple_client(self, timeout=None):
        rpc = RPC(self, self.remote_ws_address, conn_timeout=timeout)
        return RPCSimpleClient(rpc)

    def add_session(self, session):
        WebSocketRPCFactory.add_session(self, session)
        if not self._deferred.called:
            self._deferred.callback(session)

    def _reconnect(self, *_):
        logger.info("WebSocket RPC: reconnecting to {}".format(self.remote_ws_address))
        conn_deferred = task.deferLater(self.reactor, self._reconnect_timeout, self.connect)
        conn_deferred.addCallback(self._client_reconnected)
        conn_deferred.addErrback(self._reconnect)

    def _client_connected(self, *_):
        logger.info("WebSocket RPC: connection to {} established".format(self.remote_ws_address))
        addr = self.connector.transport.socket.getsockname()
        self.local_host = addr[0]
        self.local_port = addr[1]

    def _client_reconnected(self, *_):
        session = self.get_session(self.remote_host, self.remote_port)
        if session:
            session.retry_requests()

    def clientConnectionLost(self, connector, reason):
        logger.info("WebSocket RPC: connection to {} lost".format(self.remote_ws_address))

        if self.on_disconnect:
            self.on_disconnect(reason)
        else:
            self._reconnect()

    def clientConnectionFailed(self, connector, reason):
        logger.error("WebSocket RPC: connection to {} failed".format(self.remote_ws_address))
        self._deferred.errback(reason)
