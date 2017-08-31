import unittest
from devp2p.peermanager import PeerManager
from golem.network.p2p.golemservice import GolemService
from mock import patch
import tempfile
from devp2p.peer import Peer
from devp2p.multiplexer import Packet

def override_ip_info(*_, **__):
    from golem.network.stun.pystun import OpenInternet
    return OpenInternet, '1.2.3.4', 40102

def create_client(datadir):
    # executed in a subprocess
    from golem.network.stun import pystun
    pystun.get_ip_info = override_ip_info

    from golem.client import Client
    return Client(datadir=datadir,
                  use_monitor=False,
                  transaction_system=False,
                  connect_to_known_hosts=False,
                  use_docker_machine_manager=False,
                  estimated_lux_performance=1000.0,
                  estimated_blender_performance=1000.0)

class TestGolemService(unittest.TestCase):

    def setUp(self):
        datadir = tempfile.mkdtemp(prefix='golem_service_1')
        self.client = create_client(datadir)
        self.client.connect()

    def tearDown(self):
        self.client.quit()

    @patch('gevent._socket2.socket')
    @patch('devp2p.peer.Peer.send_packet')
    @patch('golem.network.p2p.golemservice.GolemService.on_wire_protocol_start')
    def test_broadcast(self, on_wire_protocol_start, send_packet, socket):
        gservice = self.client.services.golemservice
        peer = Peer(self.client.services.peermanager, socket)
        peer.remote_pubkey = "f325434534jfdslgfds0"
        peer.connect_service(gservice)
        self.client.services.peermanager.peers.append(peer)
        gservice.get_tasks()
        pkt = Packet(prioritize=False, payload=b'\xc0', cmd_id=0, protocol_id=18317)
        peer.stop()
        peer.send_packet.assert_called_once_with(pkt)
        gservice.on_wire_protocol_start.assert_called_once()
