import unittest
import logging
import sys
import os
import time

sys.path.append(os.environ.get('GOLEM'))

from golem.network.p2p.P2PServer import P2PServer, NetServerFactory
from golem.network.p2p.NetConnState import NetConnState

class P2PService():
    def __init__(self):
        self.session = None

    def new_connection(self, session):
        self.session = session

class ConfigDesc:
    def __init__(self):
        self.start_port = 1332
        self.end_port = 1333

class testP2PServer(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.DEBUG)

    def testInit(self):
        config_desc = ConfigDesc()
        p2pServer = P2PServer(config_desc, 'p2pService')
        self.assertIsNotNone(p2pServer)
        self.assertGreaterEqual(p2pServer.curPort, config_desc.start_port)
        self.assertLessEqual(p2pServer.curPort, config_desc.end_port)

    def testNewConnection(self):
        p2pService = P2PService()
        p2pServer = P2PServer( ConfigDesc(), p2pService)
        p2pServer.new_connection('newsession')
        self.assertEquals(p2pService.session, 'newsession')

    def testChangeConfig(self):
        p2pServer = P2PServer(ConfigDesc(), 'p2pService')
        config_desc2 = ConfigDesc()
        config_desc2.start_port = 1334
        config_desc2.end_port = 1335
        p2pServer.change_config(config_desc2)
        time.sleep(1)
        self.assertEquals(p2pServer.config_desc.start_port, 1334)
        self.assertEquals(p2pServer.config_desc.end_port, 1335)
        self.assertGreaterEqual(p2pServer.curPort, config_desc2.start_port)
        self.assertLessEqual(p2pServer.curPort, config_desc2.end_port)


class testNetServerFactory(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.DEBUG)

    def testInit(self):
        self.assertIsNotNone(NetServerFactory('p2pserver'))

    def testBuildProtocol(self):
        nsf = NetServerFactory('p2pserver')
        self.assertIsInstance(nsf.buildProtocol('addr'), NetConnState)


if __name__ == '__main__':
    unittest.main()