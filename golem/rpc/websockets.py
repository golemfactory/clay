import logging
import os
import random
import time
from collections import deque

from OpenSSL import SSL
from OpenSSL import crypto
from golem.core.simpleenv import get_local_datadir

from golem.core.keysauth import KeysAuth
from twisted.web.server import Site
from twisted.web.static import File

from twisted.internet import ssl

from autobahn.twisted import WebSocketServerProtocol
from autobahn.twisted.websocket import WebSocketClientProtocol, \
    WebSocketServerFactory, WebSocketClientFactory
from twisted.internet import task
from twisted.internet.defer import Deferred
from twisted.internet.tcp import Port

from golem.core.simpleserializer import DILLSerializer
from golem.rpc.exceptions import RPCNotConnected, RPCServiceError, RPCProtocolError, \
    RPCMessageError
from golem.rpc.messages import RPCRequestMessage, RPCResponseMessage, PROTOCOL_VERSION, RPCBatchRequestMessage, \
    RPCAuthRequestMessage, RPCAuthRequiredMessage, RPCAuthResponseMessage, RPCAuthMessage
from golem.rpc.service import RPCProxyService, RPCProxyClient, RPCAddress, RPC, RPCServiceInfo

logger = logging.getLogger(__name__)


RECONNECT_TIMEOUT = 0.5  # s
REQUEST_REMOVE_INTERVAL = 1  # s
REQUEST_REMOVE_TIMEOUT = 90  # s


class WebSocketAddress(RPCAddress):

    def __init__(self, host, port, use_ssl=True):
        if use_ssl:
            protocol = u'wss'
        else:
            protocol = u'ws'
        super(WebSocketAddress, self).__init__(host, port,
                                               protocol=protocol)

    @staticmethod
    def from_connector(connector, use_ssl=True):

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

        return WebSocketAddress(host, port, use_ssl=use_ssl)


class WebSocketSSLContext(object):

    CERT_CONTENT_TYPE = 'application/x-x509-ca-cert'

    def __init__(self, cert_manager):
        self.cert_manager = cert_manager

    def create(self):
        context_factory = ssl.DefaultOpenSSLContextFactory(self.cert_manager.key_path,
                                                           self.cert_manager.cert_path)
        context = context_factory.getContext()

        # explicitly disable SSLv2, SSLv3 and old TLS
        context.set_options(SSL.OP_NO_SSLv2)
        context.set_options(SSL.OP_NO_SSLv3)
        context.set_options(SSL.OP_NO_TLSv1)

        file_server_factory = File(self.cert_manager.cert_path)
        file_server_factory.contentTypes['.crt'] = self.CERT_CONTENT_TYPE
        file_server_factory.contentTypes['.pem'] = self.CERT_CONTENT_TYPE
        cert_server_factory = Site(file_server_factory)

        return cert_server_factory, context_factory


class WebSocketCertManager(object):

    _CERT_NAME = "golem_rpc_certificate.crt"
    _PRIVATE_KEY_NAME = "golem_rpc_private_key.pem"

    def __init__(self, datadir):
        self._keys_dir = KeysAuth.get_keys_dir(datadir)
        self._certs_dir = self.get_certs_dir(datadir)

        self.key_path = os.path.join(self._keys_dir, self._PRIVATE_KEY_NAME)
        self.cert_path = os.path.join(self._certs_dir, self._CERT_NAME)

        if not os.path.exists(self.key_path) or not os.path.exists(self.cert_path):
            self._create_self_signed_certificate()
        else:
            logger.info("WebSocketCertManager: Using an existing certificate")

    @classmethod
    def get_certs_dir(cls, datadir):
        if datadir is None:
            datadir = get_local_datadir('default')
        certs_dir = os.path.join(datadir, 'certs')
        if not os.path.isdir(certs_dir):
            os.makedirs(certs_dir)
        return certs_dir

    def _create_self_signed_certificate(self, **entity):

        logger.info("WebSocketCertManager: Creating RSA key pair")
        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, 2048)

        logger.info("WebSocketCertManager: Creating a self-signed certificate")
        cert = crypto.X509()
        cert_subject = cert.get_subject()

        self._apply_to_subject(cert_subject, **entity)

        cert.set_serial_number(random.randint(0, 10 * 10 ** 18))
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(5 * 365 * 24 * 60 * 60)

        cert.set_issuer(cert_subject)
        cert.set_pubkey(key)
        cert.sign(key, 'sha1')

        self._save_key(key)
        self._save_certificate(cert)

    def _save_key(self, keys):
        with open(self.key_path, "wt") as key_file:
            key_file.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, keys))

    def _save_certificate(self, cert):
        with open(self.cert_path, "wt") as cert_file:
            cert_file.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))

    @classmethod
    def _apply_to_subject(cls, cert_subject, **entity):
        cert_subject.C = entity.pop('C', 'PL')
        cert_subject.ST = entity.pop('ST', '-')
        cert_subject.L = entity.pop('L', '-')
        cert_subject.O = entity.pop('O', '-')
        cert_subject.OU = entity.pop('OU', '-')
        cert_subject.CN = entity.pop('CN', 'Golem.self-signed')


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


class MessageParserMixin(SerializerMixin):

    def receive_message(self, message, *_):
        msg = self.deserialize(message)

        if msg.protocol_version != PROTOCOL_VERSION:
            raise RPCProtocolError("Invalid protocol version")
        elif not msg.id:
            raise RPCMessageError("Invalid message id")

        return msg

    def prepare_message(self, message, *_):
        return self.serialize(message)


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

    def get_session(self, host, port):
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
        self._authenticated = False

    def onOpen(self):
        self.factory.add_session(self)
        if not self._requests_task.running:
            self._requests_task.start(REQUEST_REMOVE_INTERVAL)
        self._retry_auth()
        self._retry_requests()

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

        if isinstance(message, RPCAuthRequestMessage):
            self._on_auth_request(message)

        elif isinstance(message, RPCAuthResponseMessage):
            self._on_auth_response(message)

        elif isinstance(message, RPCAuthRequiredMessage):
            self._retry_auth()

        elif not self._authenticated:
            self.send_message(RPCAuthRequiredMessage(), new_request=False)

        elif isinstance(message, RPCRequestMessage):
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
        else:
            is_auth = isinstance(message, RPCAuthMessage)
            if is_auth or self._authenticated:
                self.sendMessage(prepared, isBinary=True)

        return deferred

    def _on_auth_request(self, message):
        if self._authenticated or not self.factory.isServer:
            return

        self._authenticated = self.factory.check_password(message.password)
        self.send_message(RPCAuthResponseMessage(self._authenticated), new_request=False)
        if self._authenticated:
            self._retry_requests()

    def _on_auth_response(self, message):
        if self._authenticated or self.factory.isServer:
            return

        self._authenticated = message.verdict
        if self._authenticated:
            self._retry_requests()
        else:
            raise Exception("RPC: Invalid password")

    def _retry_auth(self):
        if not self.factory.isServer:
            message = RPCAuthRequestMessage(self.factory.get_password())
            self.send_message(message, new_request=False)

    def _retry_requests(self):
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

    def __init__(self, password=None):
        MessageLedger.__init__(self)
        SessionManager.__init__(self)

        self.services = []
        self.local_host = None
        self.local_port = None
        self._password = password

    def add_service(self, service):
        if not self.local_host:
            raise RPCNotConnected("Not connected")

        self.services.append(RPCProxyService(service))
        ws_address = WebSocketAddress(self.local_host, self.local_port, self.isSecure)

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

    def check_password(self, password):
        return password == self._password

    def get_password(self):
        return self._password


class WebSocketRPCServerFactory(WebSocketRPCFactory, WebSocketServerFactory):

    protocol = WebSocketRPCServerProtocol

    def __init__(self, interface='', port=0, port_cert=0, password=None,
                 ssl_context=None, serializer=None, *args, **kwargs):

        WebSocketServerFactory.__init__(self, *args, **kwargs)
        WebSocketRPCFactory.__init__(self, password=password)

        self.serializer = serializer or DILLSerializer
        self.ssl_context = ssl_context

        self.isSecure = bool(ssl_context)
        self.isServer = True

        self.listen_interface = interface
        self.listen_port = port
        self.listen_port_cert = port_cert

    def listen(self):
        from twisted.internet import reactor

        if self.isSecure:
            cert_server_factory, context_factory = self.ssl_context.create()
            listener = reactor.listenSSL(self.listen_port,
                                         factory=self,
                                         contextFactory=context_factory,
                                         interface=self.listen_interface)
            reactor.listenSSL(self.listen_port_cert,
                              factory=cert_server_factory,
                              contextFactory=context_factory,
                              interface=self.listen_interface)
        else:
            listener = reactor.listenTCP(self.listen_port,
                                         factory=self, interface=self.listen_interface)

        ws_conn_info = WebSocketAddress.from_connector(listener, use_ssl=self.isSecure)

        self.local_host = ws_conn_info.host
        self.local_port = ws_conn_info.port

        logger.info("WebSocket RPC server listening on {}"
                    .format(ws_conn_info))


class WebSocketRPCClientFactory(WebSocketRPCFactory, WebSocketClientFactory):

    protocol = WebSocketRPCClientProtocol

    def __init__(self, remote_host, remote_port, password, serializer=None, use_ssl=True, *args, **kwargs):
        from twisted.internet import reactor

        WebSocketClientFactory.__init__(self, *args, **kwargs)
        WebSocketRPCFactory.__init__(self, password=password)

        self.reactor = reactor
        self.connector = None

        self.remote_host = remote_host
        self.remote_port = remote_port
        self.remote_ws_address = WebSocketAddress(self.remote_host, self.remote_port)

        self.serializer = serializer or DILLSerializer

        self.isSecure = use_ssl
        self.isServer = False

        self._reconnect_timeout = kwargs.pop('reconnect_timeout', RECONNECT_TIMEOUT)
        self._deferred = None

    def connect(self, timeout=None):

        self._deferred = Deferred()
        self._deferred.addCallback(self._client_connected)

        logger.info("WebSocket RPC: connecting to {}".format(self.remote_ws_address))

        if self.isSecure:
            context_factory = ssl.ClientContextFactory()
            self.connector = self.reactor.connectSSL(self.remote_host, self.remote_port,
                                                     factory=self, contextFactory=context_factory, timeout=timeout)
        else:
            self.connector = self.reactor.connectTCP(self.remote_host, self.remote_port,
                                                     factory=self, timeout=timeout)

        return self._deferred

    def add_session(self, session):
        WebSocketRPCFactory.add_session(self, session)
        if not self._deferred.called:
            self._deferred.callback(session)

    def _reconnect(self, *_):
        logger.warn("WebSocket RPC: reconnecting to {}".format(self.remote_ws_address))
        conn_deferred = task.deferLater(self.reactor, self._reconnect_timeout, self.connect)
        conn_deferred.addErrback(self._reconnect)

    def _client_connected(self, *args):
        logger.info("WebSocket RPC: connection to {} established".format(self.remote_ws_address))
        addr = self.connector.transport.socket.getsockname()
        self.local_host = addr[0]
        self.local_port = addr[1]

    def clientConnectionLost(self, connector, reason):
        logger.warn("WebSocket RPC: connection to {} lost".format(self.remote_ws_address))
        self._reconnect()

    def clientConnectionFailed(self, connector, reason):
        logger.error("WebSocket RPC: connection to {} failed".format(self.remote_ws_address))
        self._deferred.errback(reason)
