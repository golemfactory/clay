import unittest
import math
import os

from mock import MagicMock

from golem.network.transport.tcpnetwork import (DataProducer, DataConsumer, FileProducer, FileConsumer,
                                                EncryptFileProducer, DecryptFileConsumer)
from golem.core.variables import BUFF_SIZE
from golem.core.keysauth import EllipticalKeysAuth
from golem.tools.captureoutput import captured_output
from golem.tools.testdirfixture import TestDirFixture


class TestDataProducerAndConsumer(unittest.TestCase):

    def test_progress(self):

        long_string = "abcdefghijklmn opqrstuvwxyz"
        short_string = "abcde"
        empty_string = ""

        self.__producer_consumer_test(short_string)
        self.__producer_consumer_test(empty_string)
        self.__producer_consumer_test(long_string, 8)
        self.__producer_consumer_test(long_string * 1000, 16)
        self.__producer_consumer_test(long_string * 10000, 128)
        self.__producer_consumer_test(long_string * 1000 * 1000 * 10)

    def __producer_consumer_test(self, data, buff_size=None):
        producer_progress_value = "Sending progress 100 %"
        consumer_progress_value = "File data receiving 100 %"
        session = MagicMock()
        if buff_size:
            d = DataProducer(data, session, buff_size)
        else:
            d = DataProducer(data, session)
            buff_size = BUFF_SIZE
        with captured_output() as (out, err):
            while session.conn.transport.unregisterProducer.call_count == 0:
                d.resumeProducing()
        min_num = math.floor(len(data) / buff_size)
        self.assertGreaterEqual(session.conn.transport.write.call_count, min_num)
        self.assertEqual(out.getvalue().strip().split("\r")[-1], producer_progress_value)
        self.assertGreaterEqual(out.getvalue().strip().split("\r"), min_num)
        self.assertEqual(err.getvalue().strip(), "")

        extra_data = {}
        c = DataConsumer(MagicMock(), extra_data)
        with captured_output() as (out, err):
            for chunk in session.conn.transport.write.call_args_list:
                c.dataReceived(chunk[0][0])
        self.assertEqual(extra_data["result"], data)
        self.assertEqual(out.getvalue().strip().split("\r")[-1], consumer_progress_value)
        self.assertGreaterEqual(out.getvalue().strip().split("\r"), min_num)
        self.assertEqual(err.getvalue().strip(), "")


class TestFileProducerAndConsumer(TestDirFixture):
    def setUp(self):
        TestDirFixture.setUp(self)
        self.tmp_file1, self.tmp_file2, self.tmp_file3 = self.additional_dir_content([1, [2]])

        long_text = "abcdefghij\nklmn opqrstuvwxy\tz"
        with open(self.tmp_file1, 'w') as f:
            f.write(long_text)
        with open(self.tmp_file3, 'w') as f:
            f.write(long_text * 10000)
        with open(self.tmp_file2, 'w'):
            pass

    def test_progress(self):
        self.__producer_consumer_test([], session=MagicMock())
        self.__producer_consumer_test([self.tmp_file1], session=MagicMock())
        self.__producer_consumer_test([self.tmp_file2], session=MagicMock())
        self.__producer_consumer_test([self.tmp_file1, self.tmp_file3], session=MagicMock())
        self.__producer_consumer_test([self.tmp_file1, self.tmp_file2, self.tmp_file3], 32, session=MagicMock())
        self.ek = EllipticalKeysAuth()
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
            with open(file) as f:
                data = f.read()
            min_num += math.floor(len(data)/buff_size)
        self.assertGreaterEqual(session.conn.transport.write.call_count, min_num)
        if len(file_list) > 0:
            self.assertEqual(out.getvalue().strip().split("\r")[-1], producer_progress_value)
            self.assertGreaterEqual(out.getvalue().strip().split("\r"), min_num)
        self.assertEqual(err.getvalue().strip(), "")

        consumer_list = ["consumer{}".format(i + 1) for i in range(len(file_list))]
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
        if len(consumer_list) > 0:
            self.assertEqual(out.getvalue().strip().split("\r")[-1], consumer_progress_value)
            self.assertGreaterEqual(out.getvalue().strip().split("\r"), min_num)
        self.assertEqual(err.getvalue().strip(), "")

