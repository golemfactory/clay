import unittest
import logging
import sys
import os
import time
from testfixtures import LogCapture

sys.path.append(os.environ.get('GOLEM'))

from golem.network.p2p.P2PService import P2PService

class ConfigDesc:
    def __init__(self):
        self.client_uid = 1
        self.seed_host = 'localhost'
        self.seed_host_port = 1233
        self.start_port = 1234
        self.end_port = 1265
        self.opt_num_peers = 2

class Peer:
    def __init__(self):
        self.taskToRemove = None
        self.address = None
        self.port = None
        self.interval = None
        self.sendGetPeersCalledCnt = 0
        self.last_message_time = time.time()

    def send_remove_task(self, task_id):
        self.taskToRemove = task_id

    def ping(self, interval):
        self.interval = interval

    def send_get_peers(self):
        self.sendGetPeersCalledCnt += 1

class TaskServer:
    def __init__(self):
        self.task_header = None
        self.task_headerToRemove = None

    def get_tasks_headers(self):
        return 'taskserver taskheaders'

    def add_task_header(self, th_dict_repr):
        self.task_header = th_dict_repr

    def remove_task_header(self, task_id):
        self.task_headerToRemove = task_id

class Session():
    def __init__(self):
        self.startCalled = False

    def start(self) :
        self.startCalled = True

class TestP2PService(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level = logging.DEBUG)
        self.config_desc = ConfigDesc()
        self.p2pservice = P2PService('hostaddr', self.config_desc)

    def testInit(self):
        self.assertIsNotNone(self.p2pservice)

    def testWrongSeedData(self):
        self.assertFalse(self.p2pservice.wrong_seed_data())
        self.p2pservice.config_desc.seed_host_port = 0
        self.assertTrue(self.p2pservice.wrong_seed_data())
        self.p2pservice.config_desc.seed_host_port = 66666
        self.assertTrue(self.p2pservice.wrong_seed_data())
        self.p2pservice.config_desc.seed_host_port = 33333
        self.assertFalse(self.p2pservice.wrong_seed_data())
        self.p2pservice.config_desc.seed_host = ''
        self.assertTrue(self.p2pservice.wrong_seed_data())

    def testSetTaskServer(self):
        new_taskServer = 'new task server'
        self.p2pservice.set_task_server(new_taskServer)
        self.assertEquals(self.p2pservice.task_server, new_taskServer)

    def testSyncNetwork(self):
        self.p2pservice.lastPeerRequest = time.time()
        time.sleep(2.5)
        peer1 = Peer()
        self.p2pservice.peers['1'] = Peer()
        self.p2pservice.sync_network()
        peer1 = self.p2pservice.peers['1']
        self.assertEquals(peer1.sendGetPeersCalledCnt , 1)
        time.sleep(2.5)
        self.p2pservice.sync_network()
        peer1 = self.p2pservice.peers['1']
        self.assertEquals(peer1.sendGetPeersCalledCnt, 2)
        self.p2pservice.peers['2'] = Peer()
        time.sleep(2.5)
        self.p2pservice.sync_network()
        peer1 = self.p2pservice.peers['1']
        self.assertEquals(peer1.sendGetPeersCalledCnt, 2)
        self.p2pservice.incoming_peers[1] = { "address": "address1", "port": 1234, "conn_trials": 0 }
        self.p2pservice.incoming_peers[2] = { "address": "address2", "port": 5678, "conn_trials": 0 }
        self.p2pservice.free_peers.append(1)
        self.p2pservice.free_peers.append(2)
        del self.p2pservice.peers['2']
        self.p2pservice.sync_network()
        self.assertGreaterEqual(sum([ x["conn_trials"] for x in self.p2pservice.incoming_peers.values() ]), 1)



    def testNewSession(self):
        session = Session()
        self.p2pservice.new_connection(session)
        self.assertTrue(session.startCalled)

    def testPingPeers(self):
        p1 = Peer()
        p2 = Peer()
        self.p2pservice.peers['1'] = p1
        self.p2pservice.peers['2'] = p2
        self.p2pservice.ping_peers(5)
        for peer in self.p2pservice.peers.values():
            self.assertEquals(peer.interval, 5)

    def testFindPeer(self):
        self.assertIsNone(self.p2pservice.find_peer('testPeerId'))
        self.p2pservice.peers['testPeer2Id'] = 'testPeer2'
        self.p2pservice.peers['testPeerId'] = 'testPeer'
        self.p2pservice.peers['testPeer3Id'] = 'testPeer3'
        self.assertEquals(self.p2pservice.find_peer('testPeerId'), 'testPeer')

    def testGetPeers(self):
        self.p2pservice.peers = 'testPeers'
        self.assertEquals(self.p2pservice.get_peers(), 'testPeers')

    def testAddPeer(self):
        self.p2pservice.add_peer('543', 'testPeer')
        self.assertEquals(self.p2pservice.peers['543'], 'testPeer')

    def testTryToAddPeer (self):
        peer_info = {'id': 'peer_id', 'address': 'address', 'port': 'port'}
        self.p2pservice.try_to_add_peer(peer_info)
        self.assertEquals(self.p2pservice.incoming_peers['peer_id']['conn_trials'], 0)
        self.assertTrue('peer_id' in self.p2pservice.free_peers)
        peer_info2 = {'id': 'peer_id', 'address': 'address2', 'port': 'port2'}
        self.p2pservice.try_to_add_peer(peer_info2)
        self.assertNotEqual(self.p2pservice.incoming_peers['peer_id']['address'], 'address2')

    def testRemovePeer(self):
        self.p2pservice.all_peers.append('345')
        self.p2pservice.peers['123'] = '345'

        self.assertTrue('345' in self.p2pservice.all_peers)
        self.assertTrue('123' in self.p2pservice.peers.keys())
        self.p2pservice.remove_peer('345')
        self.assertFalse('345' in self.p2pservice.all_peers)
        self.assertFalse('123' in self.p2pservice.peers.keys())

    def testSetLastMessage(self):
        self.p2pservice.set_last_message('type', 't', 'msg', 'addr', 1)
        self.p2pservice.set_last_message('type', 't', 'msg', 'addr', 2)
        self.p2pservice.set_last_message('type', 't', 'msg', 'addr', 3)
        self.p2pservice.set_last_message('type', 't', 'msg', 'addr', 4)
        self.p2pservice.set_last_message('type', 't', 'msg', 'addr', 5)
        self.p2pservice.set_last_message('type', 't', 'msg', 'addr', 6)
        self.assertLessEqual(len(self.p2pservice.last_messages), 5)
        self.assertEquals(self.p2pservice.last_messages[0][3], 2)
        self.assertEquals(self.p2pservice.last_messages[4][3], 6)

    def testGetLastMessages(self):
        self.p2pservice.last_messages = 'testlastmessages'
        self.assertEquals(self.p2pservice.get_last_messages(), 'testlastmessages')

    def testManagerSessionDisconnect(self):
        self.p2pservice.manager_session_disconnect('uid')
        self.assertIsNone(self.p2pservice.manager_session)

    def testChangeConfig(self):
        config_desc = ConfigDesc()
        config_desc.seed_port = '43215'
        self.p2pservice.change_config(config_desc)
        self.assertEquals(self.p2pservice.config_desc.seed_port, config_desc.seed_port)


    def testChangeAddress(self):
        with LogCapture() as l:
            self.p2pservice.change_address('bla')
            self.assertTrue('ERROR' in [ rec.levelname for rec in l.records ])

        th_dict_repr = { 'client_id': 124, 'address': 'ADDR', 'port' : 'PORT' }
        th_dict_repr_copy =  th_dict_repr.copy()
        self.p2pservice.change_address(th_dict_repr)
        self.assertDictEqual(th_dict_repr , th_dict_repr_copy)
        self.p2pservice.peers[ 124 ] = Peer()
        self.p2pservice.change_address(th_dict_repr)
        self.assertEquals( th_dict_repr['client_id'] , th_dict_repr_copy['client_id'])
        self.assertNotEquals( th_dict_repr['address'] , th_dict_repr_copy['address'])

    def testGetListenParams(self):
        expectedListenParams = (self.p2pservice.curPort, self.p2pservice.client_uid)
        self.assertEquals(self.p2pservice.get_listen_params(), expectedListenParams)

    def testGetTasksHeaders(self):
        self.p2pservice.task_server = TaskServer()
        self.assertEquals(self.p2pservice.get_tasks_headers(), 'taskserver taskheaders')

    def testAddTaskHeader(self):
        self.p2pservice.task_server = TaskServer()
        self.p2pservice.add_task_header('testHeader')
        self.assertEquals(self.p2pservice.task_server.task_header, 'testHeader')

    def testRemoveTaskHeader(self):
        self.p2pservice.task_server = TaskServer()
        self.p2pservice.remove_task_header('testHeader')
        self.assertEquals(self.p2pservice.task_server.task_headerToRemove, 'testHeader')

    def testRemoveTask(self):
        self.p2pservice.peers['1'] = Peer()
        self.p2pservice.peers['2'] = Peer()
        self.p2pservice.remove_task('555')
        for peer in self.p2pservice.peers.values():
            self.assertEquals(peer.taskToRemove, '555')
