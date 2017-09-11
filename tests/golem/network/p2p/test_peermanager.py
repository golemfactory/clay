import copy
import unittest

from ethereum.utils import encode_hex
from mock import Mock

from golem.network.p2p.peermanager import GolemPeerManager


class TestTaskPeerManagerWrapper(unittest.TestCase):

    def test_computation_capability(self):
        app = Mock(
            config=dict(
                node=dict(
                    privkey_hex=encode_hex(b'1' * 32),
                    pubkey_hex=encode_hex(b'2' * 32)
                )
            ),
            services=dict()
        )

        peer_manager = GolemPeerManager(app)
        self.assertEqual(peer_manager.computation_capability, 0)

        wrapped = copy.copy(peer_manager)
        wrapped.computation_capability = True
        self.assertEqual(wrapped.computation_capability, 1)


class TestGolemPeerManager(unittest.TestCase):
    pass
