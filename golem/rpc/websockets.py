import logging
import sys
import traceback

from autobahn.twisted import WebSocketServerProtocol
from autobahn.twisted.websocket import WebSocketClientProtocol, \
    WebSocketServerFactory, WebSocketClientFactory
from twisted.internet.defer import Deferred, inlineCallbacks, returnValue
from twisted.internet.tcp import Port

from golem.core.simpleserializer import DILLSerializer
from golem.rpc.messages import RPCRequestMessage, RPCResponseMessage, PROTOCOL_VERSION
from golem.rpc.service import ServiceNameProxy, to_names_list, to_dict

root = logging.getLogger()
root.setLevel(logging.DEBUG)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
root.addHandler(ch)

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


class WebSocketConnectionInfo(object):

    def __init__(self, conn_info):
        self.conn_info = conn_info

        if isinstance(conn_info, Port):
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
    def _get_session_key(session):
        peer = session.transport.getPeer()
        return peer.host, peer.port


class WebSocketRPCProtocol(object):

    def onOpen(self):
        try:
            self.factory.add_session(self)
        except:
            traceback.print_exc()

    def onClose(self, wasClean, code, reason):
        try:
            self.factory.remove_session(self)
        except:
            traceback.print_exc()

    def onMessage(self, payload, isBinary):
        try:
            message = self.factory.receive_message(payload, id(self))
        except:
            traceback.print_exc()
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
            try:
                self.factory.add_response(message)
            except:
                traceback.print_exc()
        else:
            logger.error("RPC: received invalid message")

    def get_sessions(self):
        return self.factory.sessions

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


class WebSocketRPCServerProtocol(WebSocketRPCProtocol, WebSocketServerProtocol):
    pass


class WebSocketRPCClientProtocol(WebSocketRPCProtocol, WebSocketClientProtocol):
    pass


class WebSocketRPCFactory(MessageLedger, SessionManager):

    def __init__(self):
        MessageLedger.__init__(self)
        SessionManager.__init__(self)

        self.services = []
        self.host = None
        self.port = None
        self.ws_conn_info = None

    def add_service(self, service):
        if not self.ws_conn_info:
            raise Exception("Not connected")

        rpc_proxy = RPCProxyService(service)
        self.services.append(rpc_proxy)
        return WebSocketRPCServiceInfo(service, self.ws_conn_info.ws_address)

    def build_client(self, service_info, timeout=None):
        rpc = RPC(self, timeout=timeout)
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
        self.port = port
        self.ws_conn_info = None

    def listen(self):
        from twisted.internet import reactor

        listen_info = reactor.listenTCP(self.port, self)
        self.ws_conn_info = WebSocketConnectionInfo(listen_info)

        logger.info("WebSocket RPC server listening on {}"
                    .format(self.ws_conn_info))


class WebSocketRPCClientFactory(WebSocketRPCFactory, WebSocketClientFactory):

    protocol = WebSocketRPCClientProtocol

    def __init__(self, host, port, serializer=None, keyring=None, *args, **kwargs):
        WebSocketClientFactory.__init__(self, *args, **kwargs)
        WebSocketRPCFactory.__init__(self)

        self.host = host
        self.port = port
        self.serializer = serializer or DILLSerializer
        self.keyring = keyring
        self.ws_conn_info = None
        self.status = Deferred()

    def connect(self):
        from twisted.internet import reactor

        connect_info = reactor.connectTCP(self.host, self.port, self)
        self.ws_conn_info = WebSocketConnectionInfo(connect_info)

        logger.info("WebSocket RPC client connecting to {}"
                    .format(self.ws_conn_info))

        return self.status

    def add_session(self, session):
        WebSocketRPCFactory.add_session(self, session)
        self.status.callback(session)

    def clientConnectionFailed(self, connector, reason):
        self.status.errback(reason)


class WebSocketRPCServiceInfo(object):

    def __init__(self, service, ws_address):
        self.method_names = to_names_list(service)
        self.ws_address = ws_address


class RPC(object):

    def __init__(self, factory, timeout=None):
        from twisted.internet import reactor

        self.reactor = reactor
        self.factory = factory
        self.host = factory.host
        self.port = factory.port
        self.timeout = timeout or 2

    @inlineCallbacks
    def call(self, method_name, *args, **kwargs):
        logger.debug("RPC call {}".format(method_name))

        session = self.factory.get_session(self.host, self.port)
        if not session:
            raise Exception("RPC: no session ({})"
                            .format(method_name))

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
