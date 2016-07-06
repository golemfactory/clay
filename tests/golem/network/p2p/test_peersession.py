import unittest

from mock import MagicMock
from random import random

from golem.network.p2p.peersession import PeerSession, logger, PeerSessionInfo
from golem.core.keysauth import EllipticalKeysAuth
from golem.tools.testwithappconfig import TestWithKeysAuth
from golem.tools.assertlogs import LogTestCase


class TestPeerSession(TestWithKeysAuth, LogTestCase):

    def test_init(self):
        ps = PeerSession(MagicMock())
        self.assertIsInstance(ps, PeerSession)

    def test_encrypt_decrypt(self):
        ps = PeerSession(MagicMock())
        ps2 = PeerSession(MagicMock())

        EllipticalKeysAuth._keys_dir = self.path
        ek = EllipticalKeysAuth(random())
        ek2 = EllipticalKeysAuth(random())
        ps.p2p_service.encrypt = ek.encrypt
        ps.p2p_service.decrypt = ek.decrypt
        ps.key_id = ek2.key_id
        ps2.p2p_service.encrypt = ek2.encrypt
        ps2.p2p_service.decrypt = ek2.decrypt
        ps2.key_id = ek.key_id

        data = "abcdefghijklm" * 1000
        self.assertEqual(ps2.decrypt(ps.encrypt(data)), data)
        self.assertEqual(ps.decrypt(ps2.encrypt(data)), data)
        with self.assertLogs(logger, level=1) as l:
            self.assertEqual(ps2.decrypt(data), data)
        self.assertTrue(any(["not encrypted" in log for log in l.output]))


class TestPeerSessionInfo(unittest.TestCase):

    def test(self):
        attributes = PeerSessionInfo.attributes
        session = MagicMock()

        for attr in attributes:
            setattr(session, attr, True)

        session.unknown_property = False
        session_info = PeerSessionInfo(session)

        for attr in attributes:
            assert hasattr(session_info, attr)
        assert not hasattr(session_info, 'unknown_property')
