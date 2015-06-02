import logging
import time
import os
import struct

from golem.resource.ResourceConnState import ResourceConnState
from golem.Message import Message, MessageHasResource, MessageWantResource, MessagePushResource, MessageDisconnect,\
    MessagePullResource, MessagePullAnswer, MessageSendResource
from golem.network.p2p.Session import NetSession

logger = logging.getLogger(__name__)

class ResourceSession(NetSession):

    ConnectionStateType = ResourceConnState

    ##########################
    def __init__( self, conn ):
        NetSession.__init__(self, conn)
        self.resourceServer = None

        self.fileSize = -1
        self.fileName = None
        self.fh = None
        self.recvSize = 0
        self.confirmation = False
        self.copies = 0
        self.buffSize = 1024

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
        locData = data
        if self.fileSize == -1:
            (self.fileSize, ) = struct.unpack( "!L", data[0:4] )
            locData = data[ 4: ]
            self.fh = open( self.resourceServer.prepareResource( self.fileName ), 'wb' )

        assert self.fh
        self.recvSize += len( locData )
        self.fh.write( locData )

        if self.recvSize == self.fileSize:
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

    #########################
    def _send(self, message):  #FIXME
        NetSession._send(self, message, sendUnverified=True)

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
            data = struct.pack( "!L", size ) + fh.read( self.buffSize )
            while data:
                self.conn.transport.write( data )
                data = fh.read( self.buffSize )

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
    def __setMsgInterpretations(self):
        self.interpretation.update( {
                                        MessagePushResource.Type: self._reactToPushResource,
                                        MessageHasResource.Type: self._reactToHasResource,
                                        MessageWantResource.Type: self._reactToWantResource,
                                        MessagePullResource.Type: self._reactToPullResource,
                                        MessagePullAnswer.Type: self._reactToPullAnswer
                                    })

        self.canBeNotEncrypted.extend(self.interpretation.keys()) #FIXME
        self.canBeUnsigned.extend(self.interpretation.keys()) #FIXME
        self.canBeUnverified.extend(self.interpretation.keys()) #FIXME


##############################################################################

class ResourceSessionFactory:
    def getSession(self, connection):
        return ResourceSession(connection)