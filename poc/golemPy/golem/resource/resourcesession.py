import logging


from golem.network.transport.message import MessageHello, MessageRandVal, MessageHasResource, MessageWantResource, \
    MessagePushResource, MessagePullResource, MessagePullAnswer, MessageSendResource
from golem.network.transport.session import BasicSafeSession
from golem.network.transport.tcpnetwork import FilesProtocol, EncryptFileProducer, DecryptFileConsumer

logger = logging.getLogger(__name__)


class ResourceSession(BasicSafeSession):
    """ Session for Golem resource network """

    ConnectionStateType = FilesProtocol

    def __init__(self, conn):
        """
        Create new session
        :param FilesProtocol conn: connection protocol implementation that this session should enhance
        :return None:
        """
        BasicSafeSession.__init__(self, conn)
        self.resource_server = self.conn.server

        self.file_name = None  # file to send right now
        self.confirmation = False  # should it send confirmation after receiving current file?
        self.copies = 0  # how many copies of current file should be pushed into network
        self.msgs_to_send = []  # messages waiting to be send (because connection hasn't been verified yet)
        self.conn_id = None

        self.__set_msg_interpretations()

    ########################
    # BasicSession methods #
    ########################

    def dropped(self):
        """ Close connection """
        BasicSafeSession.dropped(self)
        self.resource_server.remove_session(self)

    #######################
    # SafeSession methods #
    #######################

    def encrypt(self, data):
        """ Encrypt given data using key_id from this connection
        :param str data: data to be encrypted
        :return str: encrypted data or unchanged message (if resource server doesn't exist)
        """
        if self.resource_server:
            return self.resource_server.encrypt(data, self.key_id)
        logger.warning("Can't encrypt message - no resource_server")
        return data

    def decrypt(self, data):
        """ Decrypt given data using private key. If during decryption AssertionError occurred this may mean that
        data is not encrypted simple serialized message. In that case unaltered data are returned.
        :param str data: data to be decrypted
        :return str: decrypted data
        """
        if self.resource_server is None:
            return data
        try:
            data = self.resource_server.decrypt(data)
        except AssertionError:
            logger.warning("Failed to decrypt message, maybe it's not encrypted?")
        except Exception as err:
            logger.error("Failed to decrypt message {}".format(str(err)))
            assert False

        return data

    def sign(self, msg):
        """ Sign given message
        :param Message msg: message to be signed
        :return Message: signed message
        """
        msg.sig = self.resource_server.sign(msg.get_short_hash())
        return msg

    def verify(self, msg):
        """ Verify signature on given message. Check if message was signed with key_id from this connection.
        :param Message msg: message to be verified
        :return boolean: True if message was signed with key_id from this connection
        """
        verify = self.resource_server.verify_sig(msg.sig, msg.get_short_hash(), self.key_id)
        return verify

    def send(self, msg, send_unverified=False):
        """ Send given message if connection was verified or send_unverified option is set to True. Collect other
        message in the list (they should be send after verification).
        :param Message msg: message to be sent.
        :param boolean send_unverified: should message be sent even if the connection hasn't been verified yet?
        """
        if not self.verified and not send_unverified:
            self.msgs_to_send.append(msg)
            return
        BasicSafeSession.send(self, msg, send_unverified=send_unverified)

    #######################
    # FileSession methods #
    #######################

    def full_data_received(self, extra_data=None):
        """ Received all data in a stream mode. Send confirmation, if other user expects it (after push).
        If more copies should be pushed to the network add resource to the resource server list.
        :param dict|None extra_data: additional information that may be needed
        """
        if self.confirmation:
            self.send(MessageHasResource(self.file_name))
            self.confirmation = False
            if self.copies > 0:
                self.resource_server.add_resource_to_send(self.file_name, self.copies)
            self.copies = 0
        else:
            self.resource_server.resource_downloaded(self.file_name, self.address, self.port)
            self.dropped()
        self.file_name = None

    def send_has_resource(self, resource):
        """ Send has resource message
        :param str resource: resource name
        """
        self.send(MessageHasResource(resource))

    def send_want_resource(self, resource):
        """ Send want resource message
        :param str resource: resource name
        """
        self.send(MessageWantResource(resource))

    def send_push_resource(self, resource, copies=1):
        """ Send information that expected number of copies of given resource should be pushed to the network
        :param str resource: resource name
        :param int copies: number of copies
        """
        self.send(MessagePushResource(resource, copies))

    def send_pull_resource(self, resource):
        """ Send information that given resource is needed.
        :param resource: resource name
        """
        self.send(MessagePullResource(resource))

    def send_pull_answer(self, resource, has_resource):
        """ Send information if current peer has given resource and may send it
        :param str resource: resource name
        :param bool has_resource: information if user has resource
        """
        self.send(MessagePullAnswer(resource, has_resource))

    def send_hello(self):
        """ Send first hello message, that should begin the communication """
        self.send(MessageHello(client_key_id=self.resource_server.get_key_id(), rand_val=self.rand_val),
                  send_unverified=True)

    #########################
    # Reactions to messages #
    #########################

    def _react_to_push_resource(self, msg):
        copies = msg.copies - 1
        if self.resource_server.check_resource(msg.resource):
            self.send_has_resource(msg.resource)
            if copies > 0:
                self.resource_server.get_peers()
                self.resource_server.add_resource_to_send(msg.resource, copies)
        else:
            self.send_want_resource(msg.resource)
            self.file_name = msg.resource
            self.conn.stream_mode = True
            self.conn.consumer = DecryptFileConsumer([self.resource_server.prepare_resource(self.file_name)], "",
                                                     self, {})
            self.confirmation = True
            self.copies = copies

    def _react_to_has_resource(self, msg):
        self.resource_server.has_resource(msg.resource, self.address, self.port)
        self.dropped()

    def _react_to_want_resource(self, msg):
        self.conn.producer = EncryptFileProducer([self.resource_server.prepare_resource(msg.resource)], self)

    def _react_to_pull_resource(self, msg):
        has_resource = self.resource_server.check_resource(msg.resource)
        if not has_resource:
            self.resource_server.get_peers()
        self.send_pull_answer(msg.resource, has_resource)

    def _react_to_pull_answer(self, msg):
        self.resource_server.pull_answer(msg.resource, msg.has_resource, self)

    def _react_to_hello(self, msg):
        if self.key_id == 0:
            self.key_id = msg.client_key_id
            self.send_hello()
        elif self.key_id != msg.client_key_id:
            self.dropped()

        if not self.verify(msg):
            logger.error("Wrong signature for Hello msg")
            self.disconnect(ResourceSession.DCRUnverified)
            return

        self.send(MessageRandVal(msg.rand_val), send_unverified=True)

    def _react_to_rand_val(self, msg):
        if self.rand_val == msg.rand_val:
            self.verified = True
            self.resource_server.verified_conn(self.conn_id)
            for msg in self.msgs_to_send:
                self.send(msg)
            self.msgs_to_send = []
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
