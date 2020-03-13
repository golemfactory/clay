# pylint: disable=no-member,protected-access
import struct
import unittest
from unittest import mock

import semantic_version
from freezegun import freeze_time
import golem_messages
from golem_messages import exceptions as msg_exceptions
from golem_messages import message
from golem_messages import factories as msg_factories
from golem_messages.factories.datastructures import p2p as dt_p2p_factory

from golem import testutils
from golem.network.transport import tcpnetwork
from golem.network.transport.tcpnetwork import (SafeProtocol, SocketAddress,
                                                MAX_MESSAGE_SIZE, TCPNetwork)
from golem.network.transport.tcpnetwork_helpers import TCPConnectInfo
from golem.tools.assertlogs import LogTestCase

MagicMock = mock.MagicMock
gm_version = semantic_version.Version(golem_messages.__version__)


class TestConformance(unittest.TestCase, testutils.PEP8MixIn):
    PEP8_FILES = [
        'golem/network/transport/tcpnetwork.py',
        'golem/network/transport/tcpnetwork_helpers.py',
    ]


class TestBasicProtocol(LogTestCase):

    def setUp(self):
        session_mock = mock.MagicMock()
        session_mock.my_private_key = None
        session_mock.theirs_private_key = None
        self.protocol = tcpnetwork.BasicProtocol(
            mock.MagicMock(return_value=session_mock),
        )

        self.protocol.transport = mock.MagicMock()

    def test_init(self):
        self.assertFalse(self.protocol.opened)

    @mock.patch('golem_messages.load')
    def test_dataReceived(self, load_mock):
        data = b"abc"
        # can_receive() returns False
        self.protocol.dataReceived(data)

        self.protocol.connectionMade()
        self.protocol.dataReceived(data)
        self.protocol.db.clear_buffer()
        load_mock.assert_not_called()

        m = message.base.Disconnect(reason=None)
        data = m.serialize()
        packed_data = struct.pack("!L", len(data)) + data
        load_mock.return_value = m
        self.protocol.dataReceived(packed_data)
        self.assertEqual(self.protocol.session.interpret.call_args[0][0], m)

    @mock.patch(
        'golem.network.transport.tcpnetwork.BasicProtocol._load_message'
    )
    def test_dataReceived_long(self, load_mock):
        self.protocol.connectionMade()
        data = bytes([0xff] * (MAX_MESSAGE_SIZE + 1))
        self.assertIsNone(self.protocol.dataReceived(data))
        self.assertEqual(load_mock.call_count, 0)

    def hello(self, version=str(gm_version)):
        msg = msg_factories.base.HelloFactory()
        msg._version = version
        serialized = golem_messages.dump(msg, None, None)
        self.protocol.db.append_len_prefixed_bytes(serialized)
        self.protocol._data_to_messages()

    @mock.patch('golem.network.transport.tcpnetwork.BasicProtocol.send_message')
    @mock.patch('golem.network.transport.tcpnetwork.BasicProtocol.close')
    @mock.patch('golem_messages.message.base.verify_version',
                return_value=True)
    def test_golem_messages_ok(self, check_mock, close_mock, send_mock):
        version = "0.0.0"
        self.hello(version)
        check_mock.assert_called_once_with(version)
        close_mock.assert_not_called()
        send_mock.assert_not_called()

    @mock.patch('golem.network.transport.tcpnetwork.BasicProtocol.send_message')
    @mock.patch('golem.network.transport.tcpnetwork.BasicProtocol.close')
    @mock.patch('golem_messages.message.base.verify_version',
                side_effect=msg_exceptions.VersionMismatchError)
    def test_golem_messages_failed(self, check_mock, close_mock, send_mock):
        self.hello()
        check_mock.assert_called_once_with(mock.ANY)
        close_mock.assert_called_once_with()
        send_mock.assert_called_once_with(mock.ANY)
        self.assertEqual(
            send_mock.call_args[0][0].reason,
            message.base.Disconnect.REASON.ProtocolVersion,
        )


class SafeProtocolTestCase(unittest.TestCase):
    def setUp(self):
        session_mock = mock.MagicMock()
        session_mock.my_private_key = None
        session_mock.theirs_private_key = None
        self.protocol = SafeProtocol(
            MagicMock(return_value=session_mock),
            MagicMock(),
        )
        self.protocol.connectionMade()

    @mock.patch('golem_messages.load')
    def test_drop_set_task(self, load_mock):
        with freeze_time("2017-01-14 10:30:20") as frozen_datetime:
            node = dt_p2p_factory.Node()

            msg = message.p2p.SetTaskSession(
                key_id=None,
                node_info=node,
                conn_id=None,
                super_node_info=None)
            data = msg.serialize()
            packed_data = struct.pack("!L", len(data)) + data
            load_mock.return_value = msg
            for _ in range(0, 100):
                self.protocol.dataReceived(packed_data)
            self.protocol.session.interpret.assert_called_once_with(msg)
            frozen_datetime.move_to("2017-01-14 10:30:45")
            self.protocol.session.interpret.reset_mock()
            self.protocol.dataReceived(packed_data)
            self.protocol.session.interpret.assert_called_once_with(msg)


class TestSocketAddress(unittest.TestCase):

    def test_zone_index(self):
        base_address = "fe80::3"
        address = "fe80::3%eth0"
        port = 1111
        sa = SocketAddress(address, port)
        self.assertEqual(sa.address, base_address)
        assert sa.port == port

        address = "fe80::3%1"
        sa = SocketAddress(address, port)
        assert sa.address == base_address

        address = "fe80::3%en0"
        sa = SocketAddress(address, port)
        assert sa.address == base_address

        address = base_address
        sa = SocketAddress(address, port)
        assert sa.address == base_address

    def test_is_proper_address(self):
        self.assertTrue(SocketAddress.is_proper_address("127.0.0.1", 1020))
        assert not SocketAddress.is_proper_address("127.0.0.1", 0)
        assert not SocketAddress.is_proper_address("127.0.0.1", "ABC")
        assert not SocketAddress.is_proper_address("AB?*@()F*)A", 1020)


class TestTCPNetworkConnections(unittest.TestCase):

    def setUp(self):
        self.addresses = [
            SocketAddress('192.168.0.1', 40102),
            SocketAddress('192.168.0.2', 40104),
        ]

    def test_without_rate_limiter(self):
        factory = mock.Mock()
        network = TCPNetwork(factory)
        assert not network.rate_limiter

        connect = mock.Mock()
        connect_all = network._TCPNetwork__try_to_connect_to_addresses
        network._TCPNetwork__try_to_connect_to_address = connect

        connect_all(TCPConnectInfo(self.addresses, mock.Mock(), mock.Mock()))
        assert connect.called

    def test_with_rate_limiter(self):
        factory = mock.Mock()
        network = TCPNetwork(factory, limit_connection_rate=True)

        assert network.rate_limiter

        call = mock.Mock()
        connect = mock.Mock()
        connect_all = network._TCPNetwork__try_to_connect_to_addresses

        network._TCPNetwork__try_to_connect_to_address = connect
        network.rate_limiter.call = call

        connect_all(TCPConnectInfo(self.addresses, mock.Mock(), mock.Mock()))
        assert not connect.called
        assert call.called


class TestBrodcastProtocol(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.session_factory = mock.MagicMock()
        self.server = mock.MagicMock()
        self.protocol = tcpnetwork.BroadcastProtocol(
            session_factory=self.session_factory,
            server=self.server,
        )
        self.protocol.transport = mock.MagicMock()
        self.protocol.transport.loseConnection.side_effect = \
            lambda: self.protocol.connectionLost()
        self.broadcast_data = b'B\x00\x00\x00\x00\x00'  # empty
        self.msg_data = b'\x00\x00\x02\xcd\x00\x00\x00\x00\x00\x00^jJv\x00`]\x88wO\xc5z\xa9\xf5\xa9\xb1\x94\xb7\x86\xe42\xe0\r\xd9\xb3d{(a4\xe1\xbaH\xfc\x07\x9bCY\xe8l\x0b?\n\xcf\xc5g\xc3\xbb\xf30\x8f\x98\xb5\x0cK\x00\x81(\xa2\x8ffhjXO\x93\x98\xeb"\x00\x89\x82hrand_val\xfb?\xc5\xffU\xa8rlm\x82hproto_idb32\x82inode_info\xadinode_namepmainnet-gf-1 gitckeyx\x800c706778f7442d63c626dbdd7cbcf3cad62071f0328ce4987249389aad854203d13547f8f1e1a967a9cc1700f9def0d5a25d88ec5d9d596f7beb2cebbddcba13hprv_port\x19\x9c\xa7hpub_port\x19\x9c\xa7lp2p_prv_port\x19\x9c\xa6lp2p_pub_port\x19\x9c\xa6hprv_addrm172.31.57.199hpub_addrm18.197.86.211mprv_addresses\x82m172.31.57.199j172.17.0.1shyperdrive_prv_port\x19\x0c\xd2shyperdrive_pub_port\x19\x0c\xd2mport_statuses\xa3\x19\x9c\xa6dopen\x19\x9c\xa7dopen\x19\x0c\xd2dopenhnat_type\x80\x82dport\x19\x9c\xa6\x82jclient_verf0.22.1\x82osolve_challenge\xf4\x82ichallenge\xf6\x82jdifficulty\xf6\x82hmetadata\xa1kperformance\xa4gBLENDER\xfb@b\xa5\xbf\x84\xc3\xdb\x02mBLENDER_NVGPU\xfb\x00\x00\x00\x00\x00\x00\x00\x00dWASM\xfb@\x85\x91g\\\xf0vNgDEFAULT\xfb@\x9e6\xc0\x02\xfb)y\x063.14.2\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'  # noqa pylint: disable=line-too-long

    def test_no_marker(self):
        self.protocol.connectionMade()
        self.protocol.dataReceived(self.msg_data)
        self.assertTrue(self.protocol.is_disconnected())

    @mock.patch(
        'golem.network.broadcast.prepare_handshake',
        return_value=[],
    )
    @mock.patch(
        'golem.network.transport.tcpnetwork'
        '.BasicProtocol._data_to_messages',
        return_value=[],
    )
    def test_broadcast_and_message(
            self,
            mock_data_to_messages,
            mock_prepare_handshake,
    ):
        self.protocol.connectionMade()
        self.protocol.dataReceived(self.broadcast_data+self.msg_data)
        mock_data_to_messages.assert_called_once_with()
        self.assertEqual(self.protocol.db.data_size(), 721)
        mock_prepare_handshake.assert_called_once_with()
