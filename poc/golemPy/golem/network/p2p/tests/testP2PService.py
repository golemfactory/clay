import unittest
import logging
import sys
import time
from testfixtures import LogCapture

sys.path.append('./../../../../')

from golem.network.p2p.P2PService import P2PService

class ConfigDesc:
    def __init__( self ):
        self.clientUid = 1
        self.seedHost = 'localhost'
        self.seedHostPort = 1233
        self.startPort = 1234
        self.endPort = 1265
        self.optNumPeers = 2

class Peer:
    def __init__( self ):
        self.taskToRemove = None
        self.address = None
        self.port = None
        self.interval = None
        self.sendGetPeersCalledCnt = 0

    def sendRemoveTask( self, taskId ):
        self.taskToRemove = taskId

    def ping( self, interval ):
        self.interval = interval

    def sendGetPeers( self ):
        self.sendGetPeersCalledCnt += 1

class TaskServer:
    def __init__( self ):
        self.taskHeader = None
        self.taskHeaderToRemove = None

    def getTasksHeaders( self ):
        return 'taskserver taskheaders'

    def addTaskHeader( self, thDictRepr ):
        self.taskHeader = thDictRepr

    def removeTaskHeader( self, taskId ):
        self.taskHeaderToRemove = taskId

class Session():
    def __init__( self ):
        self.startCalled = False

    def start( self ) :
        self.startCalled = True

class TestP2PService( unittest.TestCase ):
    def setUp( self ):
        logging.basicConfig( level = logging.DEBUG )
        self.configDesc = ConfigDesc()
        self.p2pservice = P2PService('hostaddr', self.configDesc)

    def testInit( self ):
        self.assertIsNotNone( self.p2pservice )

    def testWrongSeedData( self ):
        self.assertFalse( self.p2pservice.wrongSeedData() )
        self.p2pservice.configDesc.seedHostPort = 0
        self.assertTrue( self.p2pservice.wrongSeedData() )
        self.p2pservice.configDesc.seedHostPort = 66666
        self.assertTrue( self.p2pservice.wrongSeedData() )
        self.p2pservice.configDesc.seedHostPort = 33333
        self.assertFalse( self.p2pservice.wrongSeedData() )
        self.p2pservice.configDesc.seedHost = ''
        self.assertTrue( self.p2pservice.wrongSeedData() )

    def testSetTaskServer( self ):
        newTaskServer = 'new task server'
        self.p2pservice.setTaskServer( newTaskServer )
        self.assertEquals( self.p2pservice.taskServer, newTaskServer )

    def testSyncNetwork( self ):
        self.p2pservice.lastPeerRequest = time.time()
        time.sleep(2.5)
        peer1 = Peer()
        self.p2pservice.peers['1'] = Peer()
        self.p2pservice.syncNetwork()
        peer1 = self.p2pservice.peers['1']
        self.assertEquals( peer1.sendGetPeersCalledCnt , 1 )
        time.sleep(2.5)
        self.p2pservice.syncNetwork()
        peer1 = self.p2pservice.peers['1']
        self.assertEquals( peer1.sendGetPeersCalledCnt, 2 )
        self.p2pservice.peers['2'] = Peer()
        time.sleep(2.5)
        self.p2pservice.syncNetwork()
        peer1 = self.p2pservice.peers['1']
        self.assertEquals( peer1.sendGetPeersCalledCnt, 2 )
        self.p2pservice.incommingPeers[1] = { "address": "address1", "port": 1234, "conn_trials": 0 }
        self.p2pservice.incommingPeers[2] = { "address": "address2", "port": 5678, "conn_trials": 0 }
        self.p2pservice.freePeers.append(1)
        self.p2pservice.freePeers.append(2)
        del self.p2pservice.peers['2']
        self.p2pservice.syncNetwork()
        self.assertGreaterEqual( sum([ x["conn_trials"] for x in self.p2pservice.incommingPeers.values() ] ), 1 )



    def testNewSession( self ):
        session = Session()
        self.p2pservice.newSession( session )
        self.assertTrue( session.startCalled )

    def testPingPeers( self ):
        p1 = Peer()
        p2 = Peer()
        self.p2pservice.peers['1'] = p1
        self.p2pservice.peers['2'] = p2
        self.p2pservice.pingPeers( 5 )
        for peer in self.p2pservice.peers.values():
            self.assertEquals( peer.interval, 5 )

    def testFindPeer( self ):
        self.assertIsNone( self.p2pservice.findPeer( 'testPeerId' ) )
        self.p2pservice.peers['testPeer2Id'] = 'testPeer2'
        self.p2pservice.peers['testPeerId'] = 'testPeer'
        self.p2pservice.peers['testPeer3Id'] = 'testPeer3'
        self.assertEquals( self.p2pservice.findPeer( 'testPeerId' ), 'testPeer' )

    def testGetPeers( self ):
        self.p2pservice.peers = 'testPeers'
        self.assertEquals( self.p2pservice.getPeers(), 'testPeers' )

    def testAddPeer( self ):
        self.p2pservice.addPeer('543', 'testPeer')
        self.assertEquals( self.p2pservice.peers['543'], 'testPeer' )

    def testTryToAddPeer ( self ):
        peerInfo = {}
        peerInfo['id'] = 'peerId'
        peerInfo['address'] = 'address'
        peerInfo['port'] = 'port'
        self.p2pservice.tryToAddPeer( peerInfo )
        self.assertEquals( self.p2pservice.incommingPeers['peerId']['conn_trials'], 0 )
        self.assertTrue( 'peerId' in self.p2pservice.freePeers )
        peerInfo2 = {}
        peerInfo2['id'] = 'peerId'
        peerInfo2['address'] = 'address2'
        peerInfo2['port'] = 'port2'
        self.p2pservice.tryToAddPeer( peerInfo2 )
        self.assertNotEqual( self.p2pservice.incommingPeers['peerId']['address'], 'address2' )

    def testRemovePeer( self ):
        self.p2pservice.allPeers.append('345')
        self.p2pservice.peers['123'] = '345'

        self.assertTrue( '345' in self.p2pservice.allPeers )
        self.assertTrue( '123' in self.p2pservice.peers.keys())
        self.p2pservice.removePeer( '345' )
        self.assertFalse( '345' in self.p2pservice.allPeers )
        self.assertFalse( '123' in self.p2pservice.peers.keys() )

    def testSetLastMessage( self ):
        self.p2pservice.setLastMessage('type', 't', 'msg', 'addr', 1 )
        self.p2pservice.setLastMessage('type', 't', 'msg', 'addr', 2 )
        self.p2pservice.setLastMessage('type', 't', 'msg', 'addr', 3 )
        self.p2pservice.setLastMessage('type', 't', 'msg', 'addr', 4 )
        self.p2pservice.setLastMessage('type', 't', 'msg', 'addr', 5 )
        self.p2pservice.setLastMessage('type', 't', 'msg', 'addr', 6 )
        self.assertLessEqual( len( self.p2pservice.lastMessages ), 5 )
        self.assertEquals( self.p2pservice.lastMessages[0][3], 2 )
        self.assertEquals( self.p2pservice.lastMessages[4][3], 6 )

    def testGetLastMessages( self ):
        self.p2pservice.lastMessages = 'testlastmessages'
        self.assertEquals( self.p2pservice.getLastMessages(), 'testlastmessages' )

    def testManagerSessionDisconnect( self ):
        self.p2pservice.managerSessionDisconnect( 'uid' )
        self.assertIsNone( self.p2pservice.managerSession )

    def testChangeConfig( self ):
        configDesc = ConfigDesc()
        configDesc.seedPort = '43215'
        self.p2pservice.changeConfig( configDesc )
        self.assertEquals(self.p2pservice.configDesc.seedPort, configDesc.seedPort)


    def testChangeAddress( self ):
        with LogCapture() as l:
            self.p2pservice.changeAddress( 'bla' )
            self.assertTrue( 'ERROR' in [ rec.levelname for rec in l.records ] )

        thDictRepr = { 'clientId': 124, 'address': 'ADDR', 'port' : 'PORT' }
        thDictReprCopy =  thDictRepr.copy()
        self.p2pservice.changeAddress( thDictRepr )
        self.assertDictEqual( thDictRepr , thDictReprCopy )
        self.p2pservice.peers[ 124 ] = Peer()
        self.p2pservice.changeAddress( thDictRepr )
        self.assertEquals(  thDictRepr['clientId'] , thDictReprCopy['clientId'] )
        self.assertNotEquals(  thDictRepr['address'] , thDictReprCopy['address'] )

    def testGetListenParams( self ):
        expectedListenParams = ( self.p2pservice.p2pServer.curPort, self.p2pservice.configDesc.clientUid )
        self.assertEquals( self.p2pservice.getListenParams(), expectedListenParams )

    def testGetTasksHeaders( self ):
        self.p2pservice.taskServer = TaskServer()
        self.assertEquals( self.p2pservice.getTasksHeaders(), 'taskserver taskheaders' )

    def testAddTaskHeader( self ):
        self.p2pservice.taskServer = TaskServer()
        self.p2pservice.addTaskHeader('testHeader')
        self.assertEquals( self.p2pservice.taskServer.taskHeader, 'testHeader' )

    def testRemoveTaskHeader( self ):
        self.p2pservice.taskServer = TaskServer()
        self.p2pservice.removeTaskHeader('testHeader')
        self.assertEquals( self.p2pservice.taskServer.taskHeaderToRemove, 'testHeader' )

    def testRemoveTask( self ):
        self.p2pservice.peers['1'] = Peer()
        self.p2pservice.peers['2'] = Peer()
        self.p2pservice.removeTask('555')
        for peer in self.p2pservice.peers.values():
            self.assertEquals( peer.taskToRemove, '555' )
