import unittest
import logging
import sys
import time

sys.path.append('./../../../../')

from golem.network.p2p.PeerSession import PeerSession
from golem.network.p2p.NetConnState import NetConnState
from golem.Message import MessageHello, MessagePing, MessageGetTasks, MessageGetPeers, \
                          MessagePing, MessageDisconnect, MessagePong, MessagePeers, \
                          MessageTasks, MessageRemoveTask, MessageWantToComputeTask

class Conn():
    def __init__( self ):
        self.transport = Transport()
        self.messages = []
        self.closedCalled = False

    def sendMessage( self, message ):
        self.messages.append( message )
        return True

    def isOpen( self ):
        return True

    def close( self ):
        self.closedCalled = True

class Transport():
    def getPeer( self ):
        return Peer()


class Peer():
    def __init__( self, id = 0 ):
        self.host = 'host'
        self.port = 'port'
        self.id = id

class P2PService():
    def __init__( self ):
        self.addPeerCalled = False
        self.peers = {}
        self.tasksHeaders = []
        self.peersToAdd = set()
        self.taskHeaderToRemove = None

    def getListenParams( self ):
        return 12345, 'ABC'

    def setLastMessage( self, *args):
        pass

    def removePeer( self, peer ):
        pass

    def findPeer( self, id ):
        return None

    def addPeer( self, id, peer ):
        self.addPeerCalled = True

    def getTasksHeaders( self ):
        return self.tasksHeaders

    def addTaskHeader( self, thDict ):
        self.tasksHeaders.append( thDict )
        return True

    def tryToAddPeer( self, peer ):
        self.peersToAdd.add( peer[ "id" ] )

    def removeTaskHeader( self, taskId ):
        self.taskHeaderToRemove = taskId

class TestPeerSession( unittest.TestCase ):
    def setUp( self ):
        logging.basicConfig( level = logging.DEBUG )
        self.conn = Conn()
        self.peerSession = PeerSession( self.conn )
        self.peerSession.p2pService = P2PService()

    def testInit( self ):
        self.assertEquals( self.peerSession.state, PeerSession.StateInitialize )

    def testConnectionStateType( self ):
        self.assertEquals( PeerSession.ConnectionStateType, NetConnState)

    def testStart( self ):
        self.peerSession.start()
        self.assertEquals( self.peerSession.state, PeerSession.StateConnecting )
        self.assertIsInstance( self.conn.messages[0], MessageHello )
        self.assertIsInstance( self.conn.messages[1], MessagePing )

    def testDropped ( self ):
        self.peerSession.dropped()
        self.assertEquals( self.peerSession.state, PeerSession.StateInitialize )
        self.assertEquals( self.conn.closedCalled, True )

    def testPing( self ):
        self.peerSession.ping( 1 )
        time.sleep(2)
        self.assertIsInstance( self.conn.messages[0], MessagePing )

    def testInterpret( self ):
        self.peerSession.interpret( None )
        self.assertIsInstance( self.conn.messages[0], MessageDisconnect )
        self.assertIsNotNone( self.peerSession.lastDisconnectTime )
        self.peerSession.lastDisconnectTime = None

        self.peerSession.interpret( MessagePing() )
        self.assertIsInstance( self.conn.messages[1], MessagePong )

        self.peerSession.interpret( MessagePong() )

        self.peerSession.interpret( MessageHello() )
        self.assertTrue( self.peerSession.p2pService.addPeerCalled )
        self.assertIsInstance( self.conn.messages[2], MessageHello )
        self.assertIsInstance( self.conn.messages[3], MessagePing )

        self.peerSession.interpret( MessageGetPeers() )
        self.assertIsInstance( self.conn.messages[4], MessagePeers )

        self.peerSession.interpret( MessagePeers( [ {"id": 1} , {"id": 2} ] ) )
        self.assertSetEqual( self.peerSession.p2pService.peersToAdd, set( [1, 2] ) )

        self.peerSession.interpret( MessageTasks([ 1, 2 ]) )
        self.assertEquals( len( self.peerSession.p2pService.tasksHeaders ), 2)

        self.peerSession.interpret( MessageGetTasks() )
        self.assertIsInstance( self.conn.messages[5], MessageTasks )

        self.peerSession.interpret( MessageWantToComputeTask() )
        self.assertIsInstance( self.conn.messages[6], MessageDisconnect )

        self.peerSession.interpret( MessageRemoveTask('12345') )
        self.assertEqual( self.peerSession.p2pService.taskHeaderToRemove, '12345' )

        self.peerSession.interpret( MessageDisconnect() )
        self.assertEquals( self.conn.closedCalled, True )




    def testSendGetPeers( self ):
        self.peerSession.sendGetPeers()
        self.assertIsInstance( self.conn.messages[0], MessageGetPeers )

    def testSendGetTasks( self ):
        self.peerSession.sendGetTasks()
        self.assertIsInstance( self.conn.messages[0], MessageGetTasks )