import logging
import time
import os
import struct

from golem.resource.ResourceConnState import ResourceConnState
from golem.Message import MessageHello, MessageRandVal, MessageHasResource, MessageWantResource, MessagePushResource, MessageDisconnect,\
    MessagePullResource, MessagePullAnswer, MessageSendResource
from golem.network.p2p.Session import NetSession

logger = logging.getLogger(__name__)

class ResourceSession(NetSession):

    ConnectionStateType = ResourceConnState

    ##########################
    def __init__( self, conn ):
        NetSession.__init__(self, conn)
        self.resourceServer = None

        #FIXME Powinno byc zastapione przez FileProducer + FileConsumer
        self.fileSize = -1
        self.fileName = None
        self.fh = None
        self.recvSize = 0
        self.chunkSize = 0
        self.recvChunkSize = 0
        self.lastData = ''
        self.confirmation = False
        self.copies = 0
        self.buffSize = 5 * 1024

        self.msgsToSend = []

        self.__setMsgInterpretations()

   ##########################
    def clean(self):
        if self.fh is not None:
            self.fh.close()
            if self.recvSize < self.fileSize:
                os.remove( self.fileName)

    ##########################
    def dropped( self ):
        self.clean()
        self.conn.close()
        self.resourceServer.removeSession(self)

    ##########################
    def sendHasResource( self, resource ):
        self._send( MessageHasResource( resource ) )

    ##########################
    def sendWantResource( self, resource ):
        self._send( MessageWantResource( resource ) )

    ##########################
    def sendPushResource( self, resource, copies = 1 ):
        self._send( MessagePushResource( resource, copies ) )

    ##########################
    def sendPullResource( self, resource ):
         self._send( MessagePullResource( resource ) )

    ##########################
    def sendPullAnswer( self, resource, hasResource ):
        self._send( MessagePullAnswer( resource, hasResource ) )

    ##########################
    def sendSendResource( self, resource ):
        self._send( MessageSendResource( resource) )
        self.conn.fileMode = True

    ##########################
    def fileDataReceived( self, data ):
        locData = self.lastData + data
        if self.fileSize == -1:
            (self.fileSize, ) = struct.unpack( "!L", data[0:4] )
            locData = data[ 4: ]
            self.fh = open( self.resourceServer.prepareResource( self.fileName ), 'wb' )

        assert self.fh

        receiveNext = False
        while not receiveNext:
            if self.chunkSize == 0:
                ( self.chunkSize, ) = struct.unpack("!L", locData[ :4 ] )
                locData = locData[4:]

            self.recvChunkSize = len( locData )
            if self.recvChunkSize >= self.chunkSize:
                data = self.decrypt(locData[:self.chunkSize])
                self.fh.write(data)
                self.recvSize += len(data)
                self.lastData = locData[self.chunkSize:]
                self.recvChunkSize = 0
                self.chunkSize = 0
                locData = self.lastData

                if len(self.lastData) <= 4:
                    receiveNext = True
            else:
                self.lastData = locData
                receiveNext = True

            if self.recvSize == self.fileSize:
                receiveNext = True
                self._endReceiving()

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
            msg =  self.resourceServer.decrypt(msg)
        except AssertionError:
            logger.warning("Failed to decrypt message, maybe it's not encrypted?")
        except Exception as err:
            logger.error( "Failed to decrypt message {}".format( str(err) ) )
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
        self._send(MessageHello(clientKeyId = self.resourceServer.getKeyId(), randVal = self.randVal), sendUnverified=True)

    ##########################
    def _send(self, msg, sendUnverified=False):
        if not self.verified and not sendUnverified:
            self.msgsToSend.append(msg)
            return
        NetSession._send(self, msg, sendUnverified=sendUnverified)

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
            self.conn.fileMode = True
            self.confirmation = True
            self.copies = copies

    ##########################
    def _reactToHasResource(self, msg):
        self.resourceServer.hasResource( msg.resource, self.address, self.port )
        self.dropped()

    ##########################
    def _reactToWantResource(self, msg):
        file_ = self.resourceServer.prepareResource( msg.resource )
        size = os.path.getsize( file_ )

        with open( file_, 'rb') as fh:
            data = self.encrypt(fh.read(self.buffSize))
            data = struct.pack( "!L", size ) + struct.pack("!L", len(data)) + data
            while data:
                self.conn.transport.write( data )
                data = fh.read( self.buffSize )
                if data:
                    data = self.encrypt(data)
                    data = struct.pack( "!L", len(data)) + data

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
            logger.error( "Wrong signature for Hello msg" )
            self.disconnect( ResourceSession.DCRUnverified )
            return

        self._send( MessageRandVal( msg.randVal ), sendUnverified=True)


    ##########################
    def _reactToRandVal(self, msg):
        if self.randVal == msg.randVal:
            self.verified = True
            for msg in self.msgsToSend:
                self._send(msg)
            self.msgsToSend = []
        else:
            self.disconnect(ResourceSession.DCRUnverified)

    ##########################
    def _endReceiving(self):
        self.conn.fileMode = False
        self.fh.close()
        self.fh = None
        self.fileSize = -1
        self.recvSize = 0
        if self.confirmation:
            self._send( MessageHasResource( self.fileName ) )
            self.confirmation = False
            if self.copies > 0:
                self.resourceServer.addResourceToSend( self.fileName, self.copies)
            self.copies = 0
        else:
            self.resourceServer.resourceDownloaded( self.fileName, self.address, self.port )
            self.dropped()
        self.fileName = None

    ##########################
    def __setMsgInterpretations(self):
        self.interpretation.update( {
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