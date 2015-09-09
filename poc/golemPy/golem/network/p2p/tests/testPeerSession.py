import unittest
import logging
import sys
import time
import os

sys.path.append(os.environ.get('GOLEM'))

from golem.network.p2p.peer_session import PeerSession
from golem.network.p2p.NetConnState import NetConnState
from golem.network.transport.message import MessageHello, MessagePing, MessageGetTasks, MessageGetPeers, \
                          MessagePing, MessageDisconnect, MessagePong, MessagePeers, \
                          MessageTasks, MessageRemoveTask, MessageWantToComputeTask

class Conn():
    def __init__(self):
        self.transport = Transport()
        self.messages = []
        self.closedCalled = False

    def send_message(self, message):
        self.messages.append(message)
        return True

    def is_open(self):
        return True

    def close(self):
        self.closedCalled = True

class Transport():
    def getPeer(self):
        return Peer()


class Peer():
    def __init__(self, id = 0):
        self.host = 'host'
        self.port = 'port'
        self.id = id

class P2PService():
    def __init__(self):
        self.add_peer_called = False
        self.peers = {}
        self.tasksHeaders = []
        self.peersToAdd = set()
        self.task_headerToRemove = None

    def get_listen_params(self):
        return 12345, 'ABC'

    def set_last_message(self, *args):
        pass

    def remove_peer(self, peer):
        pass

    def find_peer(self, id):
        return None

    def add_peer(self, id, peer):
        self.add_peer_called = True

    def get_tasks_headers(self):
        return self.tasksHeaders

    def add_task_header(self, thDict):
        self.tasksHeaders.append(thDict)
        return True

    def try_to_add_peer(self, peer):
        self.peersToAdd.add(peer[ "id" ])

    def remove_task_header(self, task_id):
        self.task_headerToRemove = task_id

class TestPeerSession(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level = logging.DEBUG)
        self.conn = Conn()
        self.peer_session = PeerSession(self.conn)
        self.peer_session.p2pService = P2PService()

    def testInit(self):
        self.assertEquals(self.peer_session.state, PeerSession.StateInitialize)

    def testConnectionStateType(self):
        self.assertEquals(PeerSession.ConnectionStateType, NetConnState)

    def testStart(self):
        self.peer_session.start()
        self.assertEquals(self.peer_session.state, PeerSession.StateConnecting)
        self.assertIsInstance(self.conn.messages[0], MessageHello)
        self.assertIsInstance(self.conn.messages[1], MessagePing)

    def testDropped (self):
        self.peer_session.dropped()
        self.assertEquals(self.peer_session.state, PeerSession.StateInitialize)
        self.assertEquals(self.conn.closedCalled, True)

    def testPing(self):
        self.peer_session.ping(1)
        time.sleep(2)
        self.assertIsInstance(self.conn.messages[0], MessagePing)

    def testInterpret(self):
        self.peer_session.interpret(None)
        self.assertIsInstance(self.conn.messages[0], MessageDisconnect)
        self.assertIsNotNone(self.peer_session.last_disconnect_time)
        self.peer_session.last_disconnect_time = None

        self.peer_session.interpret(MessagePing())
        self.assertIsInstance(self.conn.messages[1], MessagePong)

        self.peer_session.interpret(MessagePong())

        self.peer_session.interpret(MessageHello())
        self.assertTrue(self.peer_session.p2pService.add_peer_called)
        self.assertIsInstance(self.conn.messages[2], MessageHello)
        self.assertIsInstance(self.conn.messages[3], MessagePing)

        self.peer_session.interpret(MessageGetPeers())
        self.assertIsInstance(self.conn.messages[4], MessagePeers)

        self.peer_session.interpret(MessagePeers([ {"id": 1} , {"id": 2} ]))
        self.assertSetEqual(self.peer_session.p2pService.peersToAdd, set([1, 2]))

        self.peer_session.interpret(MessageTasks([ 1, 2 ]))
        self.assertEquals(len(self.peer_session.p2pService.tasksHeaders), 2)

        self.peer_session.interpret(MessageGetTasks())
        self.assertIsInstance(self.conn.messages[5], MessageTasks)

        self.peer_session.interpret(MessageWantToComputeTask())
        self.assertIsInstance(self.conn.messages[6], MessageDisconnect)

        self.peer_session.interpret(MessageRemoveTask('12345'))
        self.assertEqual(self.peer_session.p2pService.task_headerToRemove, '12345')

        self.peer_session.interpret(MessageDisconnect())
        self.assertEquals(self.conn.closedCalled, True)




    def testSendGetPeers(self):
        self.peer_session.send_get_peers()
        self.assertIsInstance(self.conn.messages[0], MessageGetPeers)

    def testSendGetTasks(self):
        self.peer_session.send_get_tasks()
        self.assertIsInstance(self.conn.messages[0], MessageGetTasks)