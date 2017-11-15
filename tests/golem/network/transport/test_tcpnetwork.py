import logging
import os
import struct
from unittest import TestCase

from mock import MagicMock

from golem import testutils
from golem.core.common import config_logging
from golem.core.keysauth import EllipticalKeysAuth
from golem.core.variables import BUFF_SIZE
from golem_messages import message
from golem.network.transport.tcpnetwork import (DataProducer, DataConsumer,
                                                FileProducer, FileConsumer,
                                                EncryptFileProducer,
                                                DecryptFileConsumer,
                                                EncryptDataProducer,
                                                DecryptDataConsumer,
                                                BasicProtocol,
                                                logger, SocketAddress,
                                                MAX_MESSAGE_SIZE)
from golem.tools.assertlogs import LogTestCase
from golem.tools.captureoutput import captured_output


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

        self.ek = EllipticalKeysAuth(self.path)
        for args in datas:
            self.__producer_consumer_test(*args, data_producer_cls=EncryptDataProducer,
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
        self.assertGreaterEqual(session.conn.transport.write.call_count, min_num)
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
        self.tmp_file1, self.tmp_file2, self.tmp_file3 = self.additional_dir_content([1, [2]])

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
        self.__producer_consumer_test([self.tmp_file1, self.tmp_file3], session=MagicMock())
        self.__producer_consumer_test([self.tmp_file1, self.tmp_file2, self.tmp_file3], 32, session=MagicMock())
        self.ek = EllipticalKeysAuth(self.path)
        self.__producer_consumer_test([], file_producer_cls=EncryptFileProducer, file_consumer_cls=DecryptFileConsumer,
                                      session=self.__make_encrypted_session_mock())
        self.__producer_consumer_test([self.tmp_file1], file_producer_cls=EncryptFileProducer,
                                      file_consumer_cls=DecryptFileConsumer,
                                      session=self.__make_encrypted_session_mock())
        self.__producer_consumer_test([self.tmp_file2], file_producer_cls=EncryptFileProducer,
                                      file_consumer_cls=DecryptFileConsumer,
                                      session=self.__make_encrypted_session_mock())
        self.__producer_consumer_test([self.tmp_file1, self.tmp_file3], file_producer_cls=EncryptFileProducer,
                                      file_consumer_cls=DecryptFileConsumer,
                                      session=self.__make_encrypted_session_mock())
        self.__producer_consumer_test([self.tmp_file1, self.tmp_file2, self.tmp_file3], 32,
                                      file_producer_cls=EncryptFileProducer, file_consumer_cls=DecryptFileConsumer,
                                      session=self.__make_encrypted_session_mock())

    def __make_encrypted_session_mock(self):
        session = MagicMock()
        session.encrypt.side_effect = self.ek.encrypt
        session.decrypt.side_effect = self.ek.decrypt
        return session

    def __producer_consumer_test(self, file_list, buff_size=None, file_producer_cls=FileProducer,
                                 file_consumer_cls=FileConsumer, session=MagicMock()):
        producer_progress_value = "Sending progress 100 %"
        consumer_progress_value = "File data receiving 100 %"
        consumer_list = ["consumer{}".format(i + 1) for i in
                         range(len(file_list))]

        print('-' * 64)

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
    def test_init(self):
        protocol = BasicProtocol()
        self.assertIsInstance(protocol, BasicProtocol)
        self.assertFalse(protocol.opened)

    def test_dataReceived(self):
        data = b"abc"
        protocol = BasicProtocol()
        self.assertIsNone(protocol.dataReceived(data))
        protocol.opened = True
        self.assertIsNone(protocol.dataReceived(data))
        protocol.session = MagicMock()
        self.assertIsNone(protocol.dataReceived(data))
        protocol.db.clear_buffer()

        m = message.MessageDisconnect()
        data = m.serialize(lambda x: b'\000'*message.Message.SIG_LEN)
        packed_data = struct.pack("!L", len(data)) + data
        protocol.dataReceived(packed_data)
        self.assertEqual(protocol.session.interpret.call_args[0][0].TYPE, m.TYPE)

    def test_dataReceived_long(self):
        data = bytes([0xff] * (MAX_MESSAGE_SIZE + 1))
        protocol = BasicProtocol()
        protocol.transport = MagicMock()
        protocol.opened = True
        protocol.session = MagicMock()
        self.assertIsNone(protocol.dataReceived(data))
        protocol.transport.loseConnection.assert_called_once()

class TestSocketAddress(TestCase):
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
