import random
import time
import logging

from golem.Message import MessageDisconnect

logger = logging.getLogger(__name__)


##############################################################################

class SessionInterface:
    ##########################
    def __init__(self, conn):
        pass

    ##########################
    def dropped(self):
        pass

    ##########################
    def interpret(self, msg):
        pass

    ##########################
    def disconnect(self, reason):
        pass

##############################################################################

class NetSessionInterface(SessionInterface):
    ##########################
    def sign(self, msg):
        pass

    ##########################
    def verify(self, msg):
        pass

    ##########################
    def encrypt(self, msg):
        pass

    ##########################
    def decrypt(self, msg):
        pass

##############################################################################

class Session(SessionInterface):

    DCRBadProtocol      = "Bad protocol"
    DCRTimeout          = "Timeout"

    ##########################
    def __init__(self, conn):
        self.conn = conn

        pp = conn.transport.getPeer()
        self.address = pp.host
        self.port = pp.port

        self.lastMessageTime = time.time()
        self.lastDisconnectTime = None
        self.interpretation = { MessageDisconnect.Type: self._reactToDisconnect }

    ##########################
    def interpret(self, msg):
        self.lastMessageTime = time.time()

        #print "Receiving from {}:{}: {}".format( self.address, self.port, msg )

        if not self._checkMsg(msg):
            return

        action = self.interpretation.get(msg.getType())
        if action:
            action(msg)
        else:
            self.disconnect(Session.DCRBadProtocol)

    ##########################
    def dropped( self ):
        self.conn.close()

    ##########################
    def disconnect(self, reason):
        logger.info( "Disconnecting {} : {} reason: {}".format( self.address, self.port, reason ) )
        if self.conn.isOpen():
            if self.lastDisconnectTime:
                self.dropped()
            else:
                self._sendDisconnect(reason)
                self.lastDisconnectTime = time.time()

    ##########################
    def _sendDisconnect(self, reason):
        self._send(MessageDisconnect(reason))

    ##########################
    def _send(self, message):
        #print "Sending to {}:{}: {}".format( self.address, self.port, message )

        if not self.conn.sendMessage(message):
            self.dropped()
            return

    ##########################
    def _checkMsg(self, msg):
        if msg is None:
            self.disconnect(Session.DCRBadProtocol)
            return False
        return True

    ##########################
    def _reactToDisconnect(self, msg):
        logger.info( "Disconnect reason: {}".format(msg.reason) )
        logger.info( "Closing {} : {}".format( self.address, self.port ) )
        self.dropped()


##############################################################################

class NetSession(Session, NetSessionInterface):

    DCROldMessage       = "Message expired"
    DCRWrongTimestamp   = "Wrong timestamp"
    DCRUnverified       = "Unverifed connection"

    ##########################
    def __init__(self, conn):
        Session.__init__(self, conn)
        self.clientKeyId = 0
        self.messageTTL = 600
        self.futureTimeTolerance = 300
        self.unverifiedCnt = 10
        self.randVal = random.random()
        self.verified = False
        self.canBeUnverified = [MessageDisconnect]
        self.canBeUnsigned = [MessageDisconnect]
        self.canBeNotEncrypted = [MessageDisconnect]

    #Simple session with no encryption and no signing
    ##########################
    def sign(self, msg):
        return msg

    ##########################
    def verify(self, msg):
        return True

    ##########################
    def encrypt(self, msg):
        return msg

    ##########################
    def decrypt(self, msg):
        return msg

    #########################
    def _send(self, message, sendUnverified = False):
        if not self.verified and not sendUnverified :
            logger.info("Connection hasn't been verified yet, not sending message")
            self.unverifiedCnt -= 1
            if self.unverifiedCnt <= 0:
                self.disconnect(NetSession.DCRUnverified)
            return

        Session._send(self, message)

    ##########################
    def _checkMsg(self, msg):
        if not Session._checkMsg(self, msg):
            return False

        if not self._verifyTime(msg):
            return False

        type = msg.getType()

        if not self.verified and type not in self.canBeUnverified:
            self.disconnect( NetSession.DCRUnverified )
            return False

        if not msg.encrypted and type not in self.canBeNotEncrypted:
            self.disconnect( NetSession.DCRBadProtocol )
            return False

        if (not type in self.canBeUnsigned) and (not self.verify(msg)):
            logger.error( "Failed to verify message signature" )
            self.disconnect( NetSession.DCRUnverified )
            return False

        return True

    ##########################
    def _verifyTime(self, msg):
        if self.lastMessageTime - msg.timestamp > self.messageTTL:
            self.disconnect( NetSession.DCROldMessage )
            return False
        elif msg.timestamp - self.lastMessageTime > self.futureTimeTolerance:
            self.disconnect( NetSession.DCRWrongTimestamp )
            return False

        return True
