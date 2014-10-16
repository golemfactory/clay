import unittest
import logging
import sys
import time

sys.path.append('./../../../../')

from golem.network.p2p.P2PServer import P2PServer, NetServerFactory
from golem.network.p2p.NetConnState import NetConnState

class P2PService():
    def __init__( self ):
        self.session = None

    def newSession( self, session ):
        self.session = session

class ConfigDesc:
    def __init__( self ):
        self.startPort = 1332
        self.endPort = 1333

class testP2PServer( unittest.TestCase ):
    def setUp(self):
        logging.basicConfig(level=logging.DEBUG)

    def testInit( self ):
        configDesc = ConfigDesc()
        p2pServer = P2PServer( configDesc, 'p2pService' )
        self.assertIsNotNone( p2pServer )
        self.assertGreaterEqual( p2pServer.curPort, configDesc.startPort )
        self.assertLessEqual( p2pServer.curPort, configDesc.endPort )

    def testNewConnection( self ):
        p2pService = P2PService()
        p2pServer = P2PServer(  ConfigDesc(), p2pService )
        p2pServer.newConnection( 'newsession' )
        self.assertEquals( p2pService.session, 'newsession' )

    def testChangeConfig( self ):
        p2pServer = P2PServer( ConfigDesc(), 'p2pService' )
        configDesc2 = ConfigDesc()
        configDesc2.startPort = 1334
        configDesc2.endPort = 1335
        p2pServer.changeConfig(configDesc2)
        time.sleep(1)
        self.assertEquals( p2pServer.configDesc.startPort, 1334 )
        self.assertEquals( p2pServer.configDesc.endPort, 1335 )
        self.assertGreaterEqual( p2pServer.curPort, configDesc2.startPort )
        self.assertLessEqual( p2pServer.curPort, configDesc2.endPort )


class testNetServerFactory( unittest.TestCase ):
    def setUp( self ):
        logging.basicConfig(level=logging.DEBUG)

    def testInit( self ):
        self.assertIsNotNone( NetServerFactory( 'p2pserver' ) )

    def testBuildProtocol( self):
        nsf = NetServerFactory( 'p2pserver' )
        self.assertIsInstance( nsf.buildProtocol( 'addr' ), NetConnState )


if __name__ == '__main__':
    unittest.main()