# pylint: disable=no-member
import logging
import os
import struct
import unittest
from unittest import mock

import golem_messages
import semantic_version
from freezegun import freeze_time
from golem_messages import exceptions as msg_exceptions
from golem_messages import message

from golem import testutils
from golem.core.common import config_logging
from golem.core.keysauth import KeysAuth
from golem.core.variables import BUFF_SIZE
from golem.network.transport import tcpnetwork
from golem.network.transport.tcpnetwork import (DataProducer, DataConsumer,
                                                FileProducer, FileConsumer,
                                                EncryptFileProducer,
                                                DecryptFileConsumer,
                                                EncryptDataProducer,
                                                DecryptDataConsumer,
                                                SafeProtocol,
                                                SocketAddress,
                                                MAX_MESSAGE_SIZE, TCPNetwork)
from golem.tools.assertlogs import LogTestCase
from golem.tools.captureoutput import captured_output
from tests.factories import messages as msg_factories
from tests.factories import p2p as p2p_factories

MagicMock = mock.MagicMock
gm_version = semantic_version.Version(golem_messages.__version__)


class TestConformance(unittest.TestCase, testutils.PEP8MixIn):
    PEP8_FILES = [
        'golem/network/transport/tcpnetwork.py',
        'golem/network/transport/tcpnetwork_helpers.py',
    ]


class TestDataProducerAndConsumer(testutils.TempDirFixture):

    def test_progress(self):

        long_string = b"abcdefghijklmn opqrstuvwxyz"
        datas = (
            (b"", None),
            (b"abcde", None),
            (long_string, 8),
            (long_string * 1000, 16),
            (long_string * 1000, 128),
            # (long_string * 1000 * 1000 * 10, None)  # This takes some time.
        )

        for args in datas:
            self.__producer_consumer_test(*args, session=MagicMock())

        self.ek = KeysAuth(self.path)
        for args in datas:
            self.__producer_consumer_test(
                *args,
                data_producer_cls=EncryptDataProducer,
                data_consumer_cls=DecryptDataConsumer,
                session=self.__make_encrypted_session_mock())

    def __make_encrypted_session_mock(self):
        session = MagicMock()
        session.encrypt.side_effect = self.ek.encrypt
        session.decrypt.side_effect = self.ek.decrypt
        return session

    def __producer_consumer_test(self, data, buff_size=None,
                                 data_producer_cls=DataProducer,
                                 data_consumer_cls=DataConsumer,
                                 session=MagicMock()):
        producer_progress_value = "Sending progress 100 %"
        consumer_progress_value = "File data receiving 100 %"
        if buff_size:
            d = data_producer_cls(data, session, buff_size)
        else:
            d = data_producer_cls(data, session)
            buff_size = BUFF_SIZE
        with captured_output() as (out, err):
            while session.conn.transport.unregisterProducer.call_count == 0:
                d.resumeProducing()

        min_num = len(data) // buff_size

        split = out.getvalue().strip().split("\r")
        self.assertGreaterEqual(
            session.conn.transport.write.call_count, min_num)
        self.assertEqual(split[-1], producer_progress_value)
        self.assertGreaterEqual(len(split), min(min_num, 100))
        self.assertEqual(err.getvalue().strip(), "")

        extra_data = {}
        c = data_consumer_cls(session, extra_data)
        with captured_output() as (out, err):
            for chunk in session.conn.transport.write.call_args_list:
                c.dataReceived(chunk[0][0])

        split = out.getvalue().strip().split("\r")
        self.assertEqual(extra_data["result"], data)
        self.assertEqual(split[-1], consumer_progress_value)
        self.assertGreaterEqual(len(split), min(min_num, 100))
        self.assertEqual(err.getvalue().strip(), "")


class TestFileProducerAndConsumer(testutils.TempDirFixture):

    @classmethod
    def setUpClass(cls):
        config_logging()

    @classmethod
    def tearDownClass(cls):
        logging.shutdown()

    def setUp(self):
        testutils.TempDirFixture.setUp(self)
        self.tmp_file1, self.tmp_file2, self.tmp_file3 \
            = self.additional_dir_content([1, [2]])

        long_text = "abcdefghij\nklmn opqrstuvwxy\tz"
        with open(self.tmp_file1, 'w') as f:
            f.write(long_text)
        with open(self.tmp_file3, 'w') as f:
            f.write(long_text * 1000)
        with open(self.tmp_file2, 'w'):
            pass

    def test_progress(self):
        self.__producer_consumer_test([], session=MagicMock())
        self.__producer_consumer_test([self.tmp_file1], session=MagicMock())
        self.__producer_consumer_test([self.tmp_file2], session=MagicMock())
        self.__producer_consumer_test(
            [self.tmp_file1, self.tmp_file3], session=MagicMock())
        self.__producer_consumer_test(
            [self.tmp_file1, self.tmp_file2, self.tmp_file3],
            32,
            session=MagicMock())
        self.ek = KeysAuth(self.path)
        self.__producer_consumer_test(
            [],
            file_producer_cls=EncryptFileProducer,
            file_consumer_cls=DecryptFileConsumer,
            session=self.__make_encrypted_session_mock())
        self.__producer_consumer_test(
            [self.tmp_file1],
            file_producer_cls=EncryptFileProducer,
            file_consumer_cls=DecryptFileConsumer,
            session=self.__make_encrypted_session_mock())
        self.__producer_consumer_test(
            [self.tmp_file2],
            file_producer_cls=EncryptFileProducer,
            file_consumer_cls=DecryptFileConsumer,
            session=self.__make_encrypted_session_mock())
        self.__producer_consumer_test(
            [self.tmp_file1,
             self.tmp_file3],
            file_producer_cls=EncryptFileProducer,
            file_consumer_cls=DecryptFileConsumer,
            session=self.__make_encrypted_session_mock())
        self.__producer_consumer_test(
            [self.tmp_file1,
             self.tmp_file2,
             self.tmp_file3],
            32,
            file_producer_cls=EncryptFileProducer,
            file_consumer_cls=DecryptFileConsumer,
            session=self.__make_encrypted_session_mock())

    def __make_encrypted_session_mock(self):
        session = MagicMock()
        session.encrypt.side_effect = self.ek.encrypt
        session.decrypt.side_effect = self.ek.decrypt
        return session

    def __producer_consumer_test(
            self,
            file_list,
            buff_size=None,
            file_producer_cls=FileProducer,
            file_consumer_cls=FileConsumer,
            session=MagicMock()):
        producer_progress_value = "Sending progress 100 %"
        consumer_progress_value = "File data receiving 100 %"
        consumer_list = ["consumer{}".format(i + 1) for i in
                         range(len(file_list))]

        if buff_size:
            p = file_producer_cls(file_list, session, buff_size)
        else:
            p = file_producer_cls(file_list, session)
            buff_size = BUFF_SIZE

        with captured_output() as (out, err):
            while session.conn.transport.unregisterProducer.call_count == 0:
                p.resumeProducing()

        min_num = 0
        for file in file_list:
            with open(file, 'rb') as f:
                data = f.read()
            min_num += len(data) // buff_size

        transport = session.conn.transport
        self.assertGreaterEqual(transport.write.call_count, min_num)
        self.assertGreaterEqual(len(transport.write.call_args_list), min_num)

        split = out.getvalue().strip().split("\r")
        if len(file_list) > 0:
            self.assertEqual(split[-1], producer_progress_value)
            self.assertGreaterEqual(len(split), min(min_num, 100))
        self.assertEqual(err.getvalue().strip(), "")

        c = file_consumer_cls(consumer_list, self.path, session)
        with captured_output() as (out, err):
            for chunk in session.conn.transport.write.call_args_list:
                c.dataReceived(chunk[0][0])

        for prod, cons in zip(file_list, consumer_list):
            with open(prod) as f:
                prod_data = f.read()
            with open(os.path.join(self.path, cons)) as f:
                cons_data = f.read()
            self.assertEqual(prod_data, cons_data)

        split = out.getvalue().strip().split("\r")
        if len(consumer_list) > 0:
            self.assertEqual(split[-1], consumer_progress_value)
            self.assertGreaterEqual(len(split), min(min_num, 100))
        self.assertEqual(err.getvalue().strip(), "")


class TestBasicProtocol(LogTestCase):

    def setUp(self):
        self.protocol = tcpnetwork.BasicProtocol()
        self.protocol.session = mock.MagicMock()
        self.protocol.session.my_private_key = None
        self.protocol.session.theirs_public_key = None
        self.protocol.transport = mock.MagicMock()

    def test_init(self):
        self.assertFalse(self.protocol.opened)

    @mock.patch('golem_messages.load')
    def test_dataReceived(self, load_mock):
        data = b"abc"
        self.assertIsNone(self.protocol.dataReceived(data))
        self.protocol.opened = True
        self.assertIsNone(self.protocol.dataReceived(data))
        self.protocol.db.clear_buffer()
        self.assertEqual(load_mock.call_count, 0)

        m = message.Disconnect(reason=None)
        data = m.serialize()
        packed_data = struct.pack("!L", len(data)) + data
        load_mock.return_value = m
        self.protocol.dataReceived(packed_data)
        self.assertEqual(self.protocol.session.interpret.call_args[0][0], m)

    @mock.patch(
        'golem.network.transport.tcpnetwork.BasicProtocol._load_message'
    )
    def test_dataReceived_long(self, load_mock):
        data = bytes([0xff] * (MAX_MESSAGE_SIZE + 1))
        self.protocol.opened = True
        self.assertIsNone(self.protocol.dataReceived(data))
        self.assertEqual(load_mock.call_count, 0)

    def hello(self, version=str(gm_version)):
        msg = msg_factories.Hello()
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
            message.Disconnect.REASON.ProtocolVersion,
        )


class SafeProtocolTestCase(unittest.TestCase):
    def setUp(self):
        self.protocol = SafeProtocol(MagicMock())
        self.protocol.opened = True
        self.protocol.session = mock.MagicMock()
        self.protocol.session.my_private_key = None
        self.protocol.session.theirs_public_key = None

    @mock.patch('golem_messages.load')
    def test_drop_set_task(self, load_mock):
        with freeze_time("2017-01-14 10:30:20") as frozen_datetime:
            node = p2p_factories.Node()

            msg = message.SetTaskSession(
                key_id=None,
                node_info=node.to_dict(),
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
        assert sa.address == base_address
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
        assert SocketAddress.is_proper_address("127.0.0.1", 1020)
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

        connect_all(self.addresses, mock.Mock(), mock.Mock())
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

        connect_all(self.addresses, mock.Mock(), mock.Mock())
        assert not connect.called
        assert call.called
