import tempfile
import unittest

from devp2p.multiplexer import Packet
from devp2p.peer import Peer
from mock import patch, Mock, sentinel

from golem.network.p2p.golemservice import GolemService
from golem.network.p2p.golemprotocol import GolemProtocol


def override_ip_info(*_, **__):
    from golem.network.stun.pystun import OpenInternet
    return OpenInternet, '1.2.3.4', 40102


def create_client(datadir):
    # executed in a subprocess
    from golem.network.stun import pystun
    pystun.get_ip_info = override_ip_info

    from golem.client import Client
    client = Client(datadir=datadir,
                    use_monitor=False,
                    transaction_system=False,
                    connect_to_known_hosts=False,
                    use_docker_machine_manager=False,
                    estimated_lux_performance=1000.0,
                    estimated_blender_performance=1000.0)

    task_server = Mock(keys_auth=Mock(
        sign=lambda x: x,
        verify=lambda *_: True
    ))

    client.services['golem_service'].setup(client, task_server)
    return client


def create_proto():
        proto = Mock()
        proto.receive_get_tasks_callbacks = []
        proto.receive_task_headers_callbacks = []
        proto.receive_get_node_name_callbacks = []
        proto.receive_node_name_callbacks = []
        proto.receive_remove_task_callbacks = []
        return proto


class TestGolemService(unittest.TestCase):

    def setUp(self):
        datadir = tempfile.mkdtemp(prefix='golem_service_1')
        self.client = create_client(datadir)

    def tearDown(self):
        self.client.quit()

    @patch('gevent._socket2.socket')
    @patch('devp2p.peer.Peer.send_packet')
    @patch('golem.network.p2p.golemservice.GolemService.on_wire_protocol_start')
    def test_broadcast(self, on_wire_protocol_start, send_packet, socket):
        gservice = self.client.services['golem_service']
        peer = Peer(self.client.services['peermanager'], socket)
        peer.remote_pubkey = "f325434534jfdslgfds0"
        peer.connect_service(gservice)
        self.client.services['peermanager'].peers.append(peer)

        gservice.peer_manager.broadcast(GolemProtocol, 'get_tasks')
        pkt = Packet(prioritize=False, payload=b'\xc0', cmd_id=0,
                     protocol_id=18317)
        peer.stop()
        self.assertTrue(peer.send_packet.called)

        # signed message encapsulates the original payload
        call_pkt = peer.send_packet.call_args[0][0]
        self.assertEqual(call_pkt.cmd_id, pkt.cmd_id)
        self.assertNotEqual(call_pkt.payload, pkt.payload)

        gservice.on_wire_protocol_start.assert_called_once()

    @patch('gevent.spawn_later')
    def test_wire_proto_start(self, spawn_later):
        app = Mock(config={}, services={})
        gservice = GolemService(app)
        gservice.wire_protocol = object

        proto = create_proto()

        gservice.on_wire_protocol_start(proto)

        self.assertGreater(len(proto.receive_get_tasks_callbacks), 0)
        self.assertGreater(len(proto.receive_task_headers_callbacks), 0)
        self.assertGreater(len(proto.receive_get_node_name_callbacks), 0)
        self.assertGreater(len(proto.receive_node_name_callbacks), 0)

        spawn_later.assert_called_with(1., proto.send_get_node_name)

    def test_receive_get_tasks(self):
        app = Mock(config={}, services={})
        gservice = GolemService(app)
        gservice.wire_protocol = object
        proto = create_proto()
        gservice.on_wire_protocol_start(proto)

        def get_tasks():
            for cb in proto.receive_get_tasks_callbacks:
                cb(proto)

        get_tasks()

        proto.send_task_headers.assert_not_called()

        client = Mock()
        task_server = Mock()
        gservice.setup(client, task_server)

        task_server.get_task_headers.return_value = []
        get_tasks()

        proto.send_task_headers.assert_not_called()

        def assert_headers(headers):
            self.assertIn(sentinel.task_hdr1, headers)
            self.assertIn(sentinel.task_hdr2, headers)

        proto.send_task_headers.side_effect = assert_headers

        task_server.get_task_headers.return_value = \
            [sentinel.task_hdr1, sentinel.task_hdr2]
        get_tasks()

        self.assertTrue(proto.send_task_headers.called)


class TestGolemService2(unittest.TestCase):

    def setUp(self):
        app = Mock(config={}, services={})
        self.gservice = GolemService(app)
        self.gservice.wire_protocol = object

        self.client = Mock()
        self.task_server = Mock()
        self.gservice.setup(self.client, self.task_server)

        self.proto = create_proto()
        self.gservice.on_wire_protocol_start(self.proto)

    def test_receive_task_headers(self):
        def make_task(d):
            task = Mock()
            task.to_dict.return_value = d
            return task

        # TODO: test on actual task headers
        task_headers = [make_task(sentinel.th_dict1),
                        make_task(sentinel.th_dict2)]

        for cb in self.proto.receive_task_headers_callbacks:
            cb(self.proto, task_headers=task_headers)

        self.task_server.add_task_header.assert_any_call(sentinel.th_dict1)
        self.task_server.add_task_header.assert_any_call(sentinel.th_dict2)

    # TODO: implement task events (new, update, remove)
    @unittest.skip('Not implemented')
    def test_receive_remove_task(self):
        task_id = b'abcdef' * 5

        for cb in self.proto.receive_remove_task_callbacks:
            cb(self.proto, task_id=task_id)

        self.task_server.remove_task_header.assert_called_with(task_id)

    def test_receive_get_node_name(self):
        name = "I AM NODE"
        self.client.config_desc.node_name = name

        for cb in self.proto.receive_get_node_name_callbacks:
            cb(self.proto)

        self.proto.send_node_name.assert_called_with(name)

    def test_receive_node_name(self):
        name = "I'm different"

        for cb in self.proto.receive_node_name_callbacks:
            cb(self.proto, node_name=name)

        self.assertEqual(name, self.proto.peer.node_name)
