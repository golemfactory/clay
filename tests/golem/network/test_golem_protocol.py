import unittest
from devp2p.service import WiredService
from devp2p.app import BaseApp
from golem.network.golem_protocol import GolemProtocol


class ProtocolMessageTest(unittest.TestCase):
    def setUp(self):
        self.config = {}  # Required in Peer object by the Protocol
        self.proto = GolemProtocol(self, WiredService(BaseApp()))
        self.packet = None  # Placeholder for a sent packet

    def send_packet(self, packet):
        """Mock of Peer.send_packet"""
        self.packet = packet

    def loopback_message(self, msg_name, *args):
        """Helper for creating, sending and receiving (parsing) a message."""
        assert self.packet is None
        getattr(self.proto, 'send_' + msg_name)(*args)
        assert self.packet is not None
        callbacks = getattr(self.proto, 'receive_' + msg_name + '_callbacks')
        assert len(callbacks) == 0
        msg_data = {}
        callbacks.append(lambda proto, **data: msg_data.update(data))
        getattr(self.proto, '_receive_' + msg_name)(self.packet)
        return msg_data

    def test_proto_start(self):
        assert isinstance(self.proto, GolemProtocol)
        self.assertFalse(self.proto)
        self.proto.start()
        self.assertTrue(self.proto)

    def test_status(self):
        """Test STATUS message of Golem Protocol"""
        data = self.loopback_message('status')
        self.assertEqual(self.proto.version, data['protocol_version'])
