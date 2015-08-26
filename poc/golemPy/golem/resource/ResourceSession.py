import logging


from golem.Message import MessageHello, MessageRandVal, MessageHasResource, MessageWantResource, MessagePushResource, MessageDisconnect,\
    MessagePullResource, MessagePullAnswer, MessageSendResource
from golem.network.transport.session import BasicSafeSession
from golem.network.transport.tcp_network import FilesProtocol, EncryptFileProducer, DecryptFileConsumer

logger = logging.getLogger(__name__)


class ResourceSession(BasicSafeSession):
    """ Session for Golem resource network """

    ConnectionStateType = FilesProtocol

    def __init__(self, conn):
        """
        Create new session
        :param Protocol conn: connection protocol implementation that this session should enhance
        :return None:
        """
        BasicSafeSession.__init__(self, conn)
        self.resource_server = self.conn.server

        self.file_name = None  # file to send right now
        self.confirmation = False
        self.copies = 0
        self.msgsToSend = []
        self.msgsToSend = []

        self.__set_msg_interpretations()

    def clean(self):
        self.conn.clean()

    def dropped(self):
        self.clean()
        self.conn.close()
        self.resource_server.removeSession(self)

    def send_has_resource(self, resource):
        self.send(MessageHasResource(resource))

    def send_want_resource(self, resource):
        self.send(MessageWantResource(resource))

    def send_push_resource(self, resource, copies=1):
        self.send(MessagePushResource(resource, copies))

    def send_pull_resource(self, resource):
        self.send(MessagePullResource(resource))

    def send_pull_answer(self, resource, has_resource):
        self.send(MessagePullAnswer(resource, has_resource))

    def encrypt(self, msg):
        if self.resource_server:
            return self.resource_server.encrypt(msg, self.key_id)
        logger.warning("Can't encrypt message - no resource_server")
        return msg

    def decrypt(self, msg):
        if not self.resource_server:
            return msg
        try:
            msg = self.resource_server.decrypt(msg)
        except AssertionError:
            logger.warning("Failed to decrypt message, maybe it's not encrypted?")
        except Exception as err:
            logger.error("Failed to decrypt message {}".format(str(err)))
            assert False

        return msg

    def sign(self, msg):
        if self.resource_server is None:
            logger.error("Task Server is None, can't sign a message.")
            return None

        msg.sign(self.resource_server)
        return msg

    def verify(self, msg):
        verify = self.resource_server.verifySig(msg.sig, msg.getShortHash(), self.key_id)
        return verify

    def send_hello(self):
        self.send(MessageHello(clientKeyId=self.resource_server.getKeyId(), randVal=self.rand_val),
                  send_unverified=True)

    def full_data_received(self, extra_data=None):
        if self.confirmation:
            self.send(MessageHasResource(self.file_name))
            self.confirmation = False
            if self.copies > 0:
                self.resource_server.addResourceToSend(self.file_name, self.copies)
            self.copies = 0
        else:
            self.resource_server.resourceDownloaded(self.file_name, self.address, self.port)
            self.dropped()
        self.file_name = None

    def data_sent(self, extra_data=None):
        self.conn.producer.close()
        self.conn.producer = None

    def production_failed(self, extra_data=None):
        self.dropped()

    def send(self, msg, send_unverified=False):
        if not self.verified and not send_unverified:
            self.msgsToSend.append(msg)
            return
        BasicSafeSession.send(self, msg, send_unverified=send_unverified)

    def _react_to_push_resource(self, msg):
        copies = msg.copies - 1
        if self.resource_server.checkResource(msg.resource):
            self.send_has_resource(msg.resource)
            if copies > 0:
                self.resource_server.getPeers()
                self.resource_server.addResourceToSend(msg.resource, copies)
        else:
            self.send_want_resource(msg.resource)
            self.file_name = msg.resource
            self.conn.stream_mode = True
            self.conn.consumer = DecryptFileConsumer([self.resource_server.prepareResource(self.file_name)],
                                                          None, self, {})
            self.confirmation = True
            self.copies = copies

    def _react_to_has_resource(self, msg):
        self.resource_server.hasResource(msg.resource, self.address, self.port)
        self.dropped()

    def _react_to_want_resource(self, msg):
        self.conn.producer = EncryptFileProducer([self.resource_server.prepareResource(msg.resource)], self)

    def _react_to_pull_resource(self, msg):
        has_resource = self.resource_server.checkResource(msg.resource)
        if not has_resource:
            self.resource_server.getPeers()
        self.send_pull_answer(msg.resource, has_resource)

    def _react_to_pull_answer(self, msg):
        self.resource_server.pullAnswer(msg.resource, msg.hasResource, self)

    def _react_to_hello(self, msg):
        if self.key_id == 0:
            self.key_id = msg.clientKeyId
            self.send_hello()

        if not self.verify(msg):
            logger.error("Wrong signature for Hello msg")
            self.disconnect(ResourceSession.DCRUnverified)
            return

        self.send(MessageRandVal(msg.randVal), send_unverified=True)

    def _react_to_rand_val(self, msg):
        if self.rand_val == msg.randVal:
            self.verified = True
            for msg in self.msgsToSend:
                self.send(msg)
            self.msgsToSend = []
        else:
            self.disconnect(ResourceSession.DCRUnverified)

    def __set_msg_interpretations(self):
        self._interpretation.update({
            MessagePushResource.Type: self._react_to_push_resource,
            MessageHasResource.Type: self._react_to_has_resource,
            MessageWantResource.Type: self._react_to_want_resource,
            MessagePullResource.Type: self._react_to_pull_resource,
            MessagePullAnswer.Type: self._react_to_pull_answer,
            MessageHello.Type: self._react_to_hello,
            MessageRandVal.Type: self._react_to_rand_val
        })

        self.can_be_not_encrypted.append(MessageHello.Type)
        self.can_be_unsigned.append(MessageHello.Type)
        self.can_be_unverified.extend([MessageHello.Type, MessageRandVal.Type])
