import unittest
import logging
import sys
import os

sys.path.append(os.environ.get('GOLEM'))

from golem.network.p2p.ConnectionState import ConnectionState
from golem.Message import Message, MessageHello
from golem.core.databuffer import DataBuffer

class Transport():
    def __init__(self):
        self.msg = None
        self.db = DataBuffer()
        self.loseConnectionCalled = False
    def getHandle(self):
        pass
    def write(self, msg):
        self.db.appendString(msg)
        self.msg  = Message.deserialize(self.db)[0]

    def loseConnection(self):
        self.loseConnectionCalled = True


class TestConnectionState(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.DEBUG)

    def testInit(self):
        connectionState = ConnectionState()
        self.assertIsNotNone(connectionState)

    def testSendMessage(self):
        connectionState = ConnectionState()
        msg = MessageHello()
        self.assertFalse(connectionState.sendMessage(msg))

        connectionState = ConnectionState()
        connectionState.opened = True
        transport = Transport()
        connectionState.transport = transport
        msg = MessageHello()
        self.assertTrue(connectionState.sendMessage(msg))
        self.assertIsInstance(transport.msg, MessageHello)

    def testClose(self):
        connectionState = ConnectionState()
        transport = Transport()
        connectionState.transport = transport
        connectionState.close()
        self.assertTrue(transport.loseConnectionCalled)

    def testIsOpen(self):
        connectionState = ConnectionState()
        self.assertFalse(connectionState.opened)




if __name__ == '__main__':
    unittest.main()