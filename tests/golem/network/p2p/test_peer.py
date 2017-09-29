import copy
import unittest

from ethereum.utils import encode_hex
from mock import Mock

from golem.network.p2p.peer import COMPUTATION_CAPABILITY, GolemPeer
from golem.network.p2p.peermanager import GolemPeerManager


class TestGolemPeer(unittest.TestCase):

    def test_capabilities(self):
        app = Mock(
            config=dict(
                node=dict(
                    privkey_hex=encode_hex(b'1' * 32),
                    pubkey_hex=encode_hex(b'2' * 32)
                ),
                client_version_string="Test 1.0"
            ),
            services=dict()
        )

        peer_manager = GolemPeerManager(app)
        peer = GolemPeer(peer_manager, Mock())

        wrapped = copy.copy(peer_manager)
        wrapped.computation_capability = True

        peer_comp = GolemPeer(wrapped, Mock())

        self.assertFalse(peer.computation_capability)
        self.assertEqual(peer.capabilities, [])

        self.assertTrue(peer_comp.computation_capability)
        self.assertEqual(peer_comp.capabilities, [(COMPUTATION_CAPABILITY, 1)])
