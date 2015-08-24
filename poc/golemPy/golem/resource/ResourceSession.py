import logging
import time
import os
import struct

from golem.Message import MessageHello, MessageRandVal, MessageHasResource, MessageWantResource, MessagePushResource, MessageDisconnect,\
    MessagePullResource, MessagePullAnswer, MessageSendResource
from golem.network.FileProducer import EncryptFileProducer
from golem.network.FileConsumer import DecryptFileConsumer
from golem.network.transport.session import BasicSafeSession
from golem.network.transport.tcp_network import FilesProtocol

logger = logging.getLogger(__name__)

class ResourceSession(BasicSafeSession):

    ConnectionStateType = FilesProtocol

    ##########################
    def __init__(self, conn):
        BasicSafeSession.__init__(self, conn)
        self.resourceServer = None

        self.fileName = None
        self.confirmation = False
        self.copies = 0
        self.msgsToSend = []
        self.msgsToSend = []

        self.__setMsgInterpretations()

   ##########################
    def clean(self):
        self.conn.clean()

    ##########################
    def dropped(self):
        self.clean()
        self.conn.close()
        self.resourceServer.removeSession(self)

    ##########################
    def sendHasResource(self, resource):
        self.send(MessageHasResource(resource))

    ##########################
    def sendWantResource(self, resource):
        self.send(MessageWantResource(resource))

    ##########################
    def sendPushResource(self, resource, copies = 1):
        self.send(MessagePushResource(resource, copies))

    ##########################
    def sendPullResource(self, resource):
         self.send(MessagePullResource(resource))

    ##########################
    def sendPullAnswer(self, resource, hasResource):
        self.send(MessagePullAnswer(resource, hasResource))

    ##########################
    def encrypt(self, msg):
        if self.resourceServer:
            return self.resourceServer.encrypt(msg, self.clientKeyId)
        logger.warning("Can't encrypt message - no resourceServer")
        return msg

    ##########################
    def decrypt(self, msg):
        if not self.resourceServer:
            return msg
        try:
            msg = self.resourceServer.decrypt(msg)
        except AssertionError:
            logger.warning("Failed to decrypt message, maybe it's not encrypted?")
        except Exception as err:
            logger.error("Failed to decrypt message {}".format(str(err)))
            assert False

        return msg


    ##########################
    def sign(self, msg):
        if self.resourceServer is None:
            logger.error("Task Server is None, can't sign a message.")
            return None

        msg.sign(self.resourceServer)
        return msg

    ##########################
    def verify(self, msg):
        verify = self.resourceServer.verifySig(msg.sig, msg.getShortHash(), self.clientKeyId)
        return verify

    ##########################
    def sendHello(self):
        self.send(MessageHello(clientKeyId = self.resourceServer.getKeyId(), randVal = self.randVal), send_unverified=True)

    ##########################
    def fullFileReceived(self, extraData):
        if self.confirmation:
            self.send(MessageHasResource(self.fileName))
            self.confirmation = False
            if self.copies > 0:
                self.resourceServer.addResourceToSend(self.fileName, self.copies)
            self.copies = 0
        else:
            self.resourceServer.resourceDownloaded(self.fileName, self.address, self.port)
            self.dropped()
        self.fileName = None

    ##########################
    def fileSent(self, fileName):
        self.conn.file_producer.clean()
        self.conn.file_producer = None

    ##########################
    def send(self, msg, send_unverified=False):
        if not self.verified and not send_unverified:
            self.msgsToSend.append(msg)
            return
        BasicSafeSession.send(self, msg, send_unverified=send_unverified)

    ##########################
    def _reactToPushResource(self, msg):
        copies = msg.copies - 1
        if self.resourceServer.checkResource(msg.resource):
            self.sendHasResource(msg.resource)
            if copies > 0:
                self.resourceServer.getPeers()
                self.resourceServer.addResourceToSend(msg.resource, copies)
        else:
            self.sendWantResource(msg.resource)
            self.fileName = msg.resource
            self.conn.file_mode = True
            self.conn.file_consumer = DecryptFileConsumer(self.resourceServer.prepareResource(self.fileName), None, self, {})
            self.confirmation = True
            self.copies = copies

    ##########################
    def _reactToHasResource(self, msg):
        self.resourceServer.hasResource(msg.resource, self.address, self.port)
        self.dropped()

    ##########################
    def _reactToWantResource(self, msg):
        self.conn.file_producer = EncryptFileProducer(self.resourceServer.prepareResource(msg.resource), self)

    ##########################
    def _reactToPullResource(self, msg):
        hasResource = self.resourceServer.checkResource(msg.resource)
        if not hasResource:
            self.resourceServer.getPeers()
        self.sendPullAnswer(msg.resource, hasResource)

    ##########################
    def _reactToPullAnswer(self, msg):
        self.resourceServer.pullAnswer(msg.resource, msg.hasResource, self)

    ##########################
    def _reactToHello(self, msg):
        if self.clientKeyId == 0:
            self.clientKeyId = msg.clientKeyId
            self.sendHello()

        if not self.verify(msg):
            logger.error("Wrong signature for Hello msg")
            self.disconnect(ResourceSession.DCRUnverified)
            return

        self.send(MessageRandVal(msg.randVal), send_unverified=True)


    ##########################
    def _reactToRandVal(self, msg):
        if self.randVal == msg.randVal:
            self.verified = True
            for msg in self.msgsToSend:
                self.send(msg)
            self.msgsToSend = []
        else:
            self.disconnect(ResourceSession.DCRUnverified)

    ##########################
    def __setMsgInterpretations(self):
        self.interpretation.update({
                                        MessagePushResource.Type: self._reactToPushResource,
                                        MessageHasResource.Type: self._reactToHasResource,
                                        MessageWantResource.Type: self._reactToWantResource,
                                        MessagePullResource.Type: self._reactToPullResource,
                                        MessagePullAnswer.Type: self._reactToPullAnswer,
                                        MessageHello.Type: self._reactToHello,
                                        MessageRandVal.Type: self._reactToRandVal
                                    })

        self.canBeNotEncrypted.append(MessageHello.Type)
        self.canBeUnsigned.append(MessageHello.Type)
        self.canBeUnverified.extend([MessageHello.Type, MessageRandVal.Type])


##############################################################################

class ResourceSessionFactory:
    def getSession(self, connection):
        return ResourceSession(connection)

    def get_session(self, connection):
        return ResourceSession(connection)