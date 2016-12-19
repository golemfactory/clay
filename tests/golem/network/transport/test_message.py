import unittest
import os
import time

from golem.core.databuffer import DataBuffer
from golem.network.transport.message import MessageWantToComputeTask, MessageReportComputedTask, Message, MessageHello
from mock import Mock, patch


class FailingMessage(Message):
    def __init__(self, *args, **kwargs):
        Message.__init__(self, *args, **kwargs)

    def dict_repr(self):
        raise Exception()


class TestMessages(unittest.TestCase):
    def test_message_want_to_compute_task(self):
        m = MessageWantToComputeTask()
        self.assertIsInstance(m, MessageWantToComputeTask)
        m = MessageWantToComputeTask("ABC", "xyz", 1000, 20, 4, 5, 3)
        self.assertEqual(m.node_name, "ABC")
        self.assertEqual(m.task_id, "xyz")
        self.assertEqual(m.perf_index, 1000)
        self.assertEqual(m.max_resource_size, 4)
        self.assertEqual(m.max_memory_size, 5)
        self.assertEqual(m.price, 20)
        self.assertEqual(m.num_cores, 3)
        self.assertEqual(m.get_type(), MessageWantToComputeTask.Type)
        dict_repr = m.dict_repr()
        m2 = MessageWantToComputeTask(dict_repr=dict_repr)
        self.assertEqual(m2.task_id, m.task_id)
        self.assertEqual(m2.node_name, m.node_name)
        self.assertEqual(m2.perf_index, m.perf_index)
        self.assertEqual(m2.max_resource_size, m.max_resource_size)
        self.assertEqual(m2.max_memory_size, m.max_memory_size)
        self.assertEqual(m2.price, m.price)
        self.assertEqual(m2.num_cores, m.num_cores)
        self.assertEqual(m.get_type(), m2.get_type())

    def test_message_report_computed_task(self):
        m = MessageReportComputedTask()
        self.assertIsInstance(m, MessageReportComputedTask)
        m = MessageReportComputedTask("xxyyzz", 0, 12034, "ABC", "10.10.10.1", 1023, "KEY_ID", "NODE", "ETH", {})
        self.assertEqual(m.subtask_id, "xxyyzz")
        self.assertEqual(m.result_type, 0)
        self.assertEqual(m.extra_data, {})
        self.assertEqual(m.computation_time, 12034)
        self.assertEqual(m.node_name, "ABC")
        self.assertEqual(m.address, "10.10.10.1")
        self.assertEqual(m.port, 1023)
        self.assertEqual(m.key_id, "KEY_ID")
        self.assertEqual(m.eth_account, "ETH")
        self.assertEqual(m.node_info, "NODE")
        self.assertEqual(m.get_type(), MessageReportComputedTask.Type)
        dict_repr = m.dict_repr()
        m2 = MessageReportComputedTask(dict_repr=dict_repr)
        self.assertEqual(m.subtask_id, m2.subtask_id)
        self.assertEqual(m.result_type, m2.result_type)
        self.assertEqual(m.extra_data, m2.extra_data)
        self.assertEqual(m.computation_time, m2.computation_time)
        self.assertEqual(m.node_name, m2.node_name)
        self.assertEqual(m.address, m2.address)
        self.assertEqual(m.port, m2.port)
        self.assertEqual(m.key_id, m2.key_id)
        self.assertEqual(m.eth_account, m2.eth_account)
        self.assertEqual(m.node_info, m2.node_info)
        self.assertEqual(m.get_type(), m2.get_type())

    def test_message_hash(self):
        m = MessageReportComputedTask("xxyyzz", 0, 12034, "ABC", "10.10.10.1", 1023, "KEY_ID", "NODE", "ETH",
                                      extra_data=MessageWantToComputeTask("ABC", "xyz", 1000, 20, 4, 5, 3))
        assert m.get_short_hash()

    def test_serialization(self):
        m = MessageReportComputedTask("xxyyzz", 0, 12034, "ABC", "10.10.10.1", 1023, "KEY_ID", "NODE", "ETH", {})
        assert m.serialize()

        m = FailingMessage(-1)
        serialized = None

        try:
            serialized = m.serialize()
        except:
            pass
        assert not serialized
        assert not Message.deserialize_message(None)

    def test_timestamp_and_timezones(self):
        epoch_t = 1475238345.0
        def set_tz(tz):
            os.environ['TZ'] = tz
            try:
                time.tzset()
            except AttributeError:
                raise unittest.SkipTest("tzset required")
        set_tz('Europe/Warsaw')
        warsaw_time = time.localtime(epoch_t)
        m = MessageHello(timestamp = epoch_t)
        db = DataBuffer()
        m.serialize_to_buffer(db)
        set_tz('US/Eastern')
        server = Mock()
        server.decrypt = lambda x: x
        msgs = Message.decrypt_and_deserialize(db, server)
        assert len(msgs) == 1
        newyork_time = time.localtime(msgs[0].timestamp)
        assert warsaw_time != newyork_time
        assert time.gmtime(epoch_t) == time.gmtime(msgs[0].timestamp)

    def test_decrypt_and_deserialize(self):
        db = DataBuffer()
        server = Mock()
        n_messages = 10

        def serialize_messages(_b):
            for m in [MessageHello() for _ in xrange(0, n_messages)]:
                m.serialize_to_buffer(_b)

        serialize_messages(db)
        server.decrypt = lambda x: x
        assert len(Message.decrypt_and_deserialize(db, server)) == n_messages

        patch_method = 'golem.network.transport.message.Message.deserialize_message'
        with patch(patch_method, side_effect=lambda x: None):
            serialize_messages(db)
            assert len(Message.decrypt_and_deserialize(db, server)) == 0

        def raise_assertion(*_):
            raise AssertionError()

        def raise_error(*_):
            raise Exception()

        server.decrypt = raise_assertion
        serialize_messages(db)

        result = Message.decrypt_and_deserialize(db, server)

        assert len(result) == n_messages
        assert all(not m.encrypted for m in result)

        server.decrypt = raise_error
        serialize_messages(db)

        result = Message.decrypt_and_deserialize(db, server)

        assert len(result) == 0
