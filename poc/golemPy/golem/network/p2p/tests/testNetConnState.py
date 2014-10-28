import unittest
import logging
import sys
import os

sys.path.append( os.environ.get( 'GOLEM' ) )

from golem.network.p2p.NetConnState import NetConnState
from golem.network.p2p.PeerSession import PeerSession
from golem.core.databuffer import DataBuffer
from golem.Message import Message, MessageHello

class Peer():
    def __init__( self ):
        self.droppedCalled = False
        self.msg = None

    def interpret ( self, msg ):
        self.msg = msg

    def dropped( self ):
        self.droppedCalled = True

class Server():
    def __init__( self ):
        self.newConnectionPeer = None

    def newConnection( self , peer ):
        self.newConnectionPeer = peer

class Transport():
    def __init__( self ):
        self.host = None
        self.port = None
    def getPeer( self ):
        return self

class TestConnectionState( unittest.TestCase ):
    def setUp(self):
        logging.basicConfig(level=logging.DEBUG)

    def testInit( self ):
        self.assertIsNotNone(NetConnState())

        self.assertIsNotNone(NetConnState('server'))

    def testSetSession( self ):
        netConnState = NetConnState()
        session = 'testSession'
        netConnState.setSession(session)
        self.assertEquals(session, netConnState.peer )

    def testConnectionMade( self ):
        netConnState = NetConnState()
        netConnState.connectionMade()
        self.assertTrue(netConnState.opened)

        server = Server()
        netConnStateServer = NetConnState( server )
        transport = Transport()
        netConnStateServer.transport = transport
        netConnStateServer.connectionMade()
        self.assertTrue(netConnStateServer.opened)
        self.assertIsInstance(netConnStateServer.peer, PeerSession)

    def testDataReceived( self ):
        netConnState = NetConnState()
        peer = Peer()
        netConnState.peer = peer
        with self.assertRaises(AssertionError):
            netConnState.dataReceived( 'data' )
        netConnState.opened = True

        netConnState.db = None
        with self.assertRaises(AssertionError):
            netConnState.dataReceived( 'data' )
        netConnState.db = DataBuffer()
        netConnState.opened = True

        self.assertIsNone( netConnState.dataReceived( 'data' ) )
        netConnState.db = DataBuffer()

        msg = MessageHello()
        db2 = DataBuffer()
        db2.appendLenPrefixedString( msg.serialize() )
        netConnState.dataReceived( db2.readAll() )
        self.assertIsInstance( peer.msg, MessageHello )

    def testConnectionLost( self ):
        netConnState = NetConnState()
        netConnState.opened = True
        peer = Peer()
        netConnState.peer = peer
        netConnState.connectionLost( 'reason' )
        self.assertFalse( netConnState.opened )
        self.assertTrue( peer.droppedCalled )

if __name__ == '__main__':
    unittest.main()