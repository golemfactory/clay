# -*- encoding: utf-8 -*-

import os
import random
import time
import unittest
import uuid

from golem.core.databuffer import DataBuffer
from golem.network.transport import message
from golem.testutils import PEP8MixIn
import mock


class FailingMessage(message.Message):
    TYPE = -1

    def __init__(self, *args, **kwargs):
        message.Message.__init__(self, *args, **kwargs)

    def dict_repr(self):
        raise Exception()


class TestMessages(unittest.TestCase, PEP8MixIn):
    PEP8_FILES = ['golem/network/transport/message.py', ]

    def setUp(self):
        random.seed()
        super(TestMessages, self).setUp()

    def test_message_want_to_compute_task(self):
        m = message.MessageWantToComputeTask()
        self.assertIsInstance(m, message.MessageWantToComputeTask)
        m = message.MessageWantToComputeTask("ABC", "xyz", 1000, 20, 4, 5, 3)
        self.assertEqual(m.node_name, "ABC")
        self.assertEqual(m.task_id, "xyz")
        self.assertEqual(m.perf_index, 1000)
        self.assertEqual(m.max_resource_size, 4)
        self.assertEqual(m.max_memory_size, 5)
        self.assertEqual(m.price, 20)
        self.assertEqual(m.num_cores, 3)
        self.assertEqual(m.TYPE, message.MessageWantToComputeTask.TYPE)
        dict_repr = m.dict_repr()
        m2 = message.MessageWantToComputeTask(dict_repr=dict_repr)
        self.assertEqual(m2.task_id, m.task_id)
        self.assertEqual(m2.node_name, m.node_name)
        self.assertEqual(m2.perf_index, m.perf_index)
        self.assertEqual(m2.max_resource_size, m.max_resource_size)
        self.assertEqual(m2.max_memory_size, m.max_memory_size)
        self.assertEqual(m2.price, m.price)
        self.assertEqual(m2.num_cores, m.num_cores)
        self.assertEqual(m.TYPE, m2.TYPE)

    def test_message_report_computed_task(self):
        m = message.MessageReportComputedTask()
        self.assertIsInstance(m, message.MessageReportComputedTask)
        m = message.MessageReportComputedTask("xxyyzz", 0, 12034, "ABC", "10.10.10.1", 1023, "KEY_ID", "NODE", "ETH", {})
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
        self.assertEqual(m.TYPE, message.MessageReportComputedTask.TYPE)
        dict_repr = m.dict_repr()
        m2 = message.MessageReportComputedTask(dict_repr=dict_repr)
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
        self.assertEqual(m.TYPE, m2.TYPE)

    def test_message_hash(self):
        m = message.MessageReportComputedTask("xxyyzz", 0, 12034, "ABC", "10.10.10.1", 1023, "KEY_ID", "NODE", "ETH",
                                              extra_data=message.MessageWantToComputeTask("ABC", "xyz", 1000, 20, 4, 5, 3))
        assert m.get_short_hash()

    def test_serialization(self):
        m = message.MessageReportComputedTask("xxyyzz", 0, 12034, "ABC", "10.10.10.1", 1023, "KEY_ID", "NODE", "ETH", {})
        assert m.serialize()

        m = FailingMessage()
        serialized = None

        try:
            serialized = m.serialize()
        except:
            pass
        assert not serialized
        assert not message.Message.deserialize_message(None)

    def test_unicode(self):
        source = unicode("test string")
        result = message.Message._unicode(source)
        assert result is source

        source = "\xd0\xd1\xd2\xd3"
        result = message.Message._unicode(source)
        assert result is source

        source = "test string"
        result = message.Message._unicode(source)
        assert type(result) is unicode
        assert result is not source
        assert result == source

        source = None
        result = message.Message._unicode(source)
        assert result is None

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
        m = message.MessageHello(timestamp=epoch_t)
        db = DataBuffer()
        m.serialize_to_buffer(db)
        set_tz('US/Eastern')
        server = mock.Mock()
        server.decrypt = lambda x: x
        msgs = message.Message.decrypt_and_deserialize(db, server)
        assert len(msgs) == 1
        newyork_time = time.localtime(msgs[0].timestamp)
        assert warsaw_time != newyork_time
        assert time.gmtime(epoch_t) == time.gmtime(msgs[0].timestamp)

    def test_decrypt_and_deserialize(self):
        db = DataBuffer()
        server = mock.Mock()
        n_messages = 10

        def serialize_messages(_b):
            for m in [message.MessageHello() for _ in xrange(0, n_messages)]:
                m.serialize_to_buffer(_b)

        serialize_messages(db)
        server.decrypt = lambda x: x
        assert len(message.Message.decrypt_and_deserialize(db, server)) == n_messages

        patch_method = 'golem.network.transport.message.Message.deserialize_message'
        with mock.patch(patch_method, side_effect=lambda x: None):
            serialize_messages(db)
            assert len(message.Message.decrypt_and_deserialize(db, server)) == 0

        def raise_assertion(*_):
            raise AssertionError()

        def raise_error(*_):
            raise Exception()

        server.decrypt = raise_assertion
        serialize_messages(db)

        result = message.Message.decrypt_and_deserialize(db, server)

        assert len(result) == n_messages
        assert all(not m.encrypted for m in result)

        server.decrypt = raise_error
        serialize_messages(db)

        result = message.Message.decrypt_and_deserialize(db, server)

        assert len(result) == 0

    def test_message_errors(self):
        m = message.MessageReportComputedTask()
        with self.assertRaises(TypeError):
            m.serialize_to_buffer("not a db")
        with self.assertRaises(TypeError):
            m.decrypt_and_deserialize("not a db")
        with self.assertRaises(TypeError):
            m.deserialize("not a db")

    def test_message_randval(self):
        rand_val = random.random()
        msg = message.MessageRandVal(rand_val=rand_val)
        expected = {
            'RAND_VAL': rand_val,
        }
        self.assertEquals(expected, msg.dict_repr())

    def test_message_challenge_solution(self):
        solution = u'O gajach świętych, z których i drew zwalonych wichrem uprzątnąć się nie godziło, opowiada Długosz (XIII, 160), że świętymi były i zwierzęta chroniące się w nich, tak iż przez ciągły ów zwyczaj czworonożne i ptactwo tych lasów, jakby domowe jakie, nie stroniło od ludzi. Skoro zważymy, że dla Litwina gaje takie były rzeczywiście nietykalnymi, że sam Mindowg nie ważył się w nie wchodzić lub różdżkę w nich ułamać, zrozumiemy to podanie. Toż samo donosi w starożytności Strabon o Henetach: były u nich dwa gaje, Hery i Artemidy, „w gajach tych ułaskawiły się zwierzęta i jelenie z wilkami się kupiły; gdy się ludzie zbliżali i dotykali ich, nie uciekały; skoro gonione od psów tu się schroniły, ustawała pogoń”. I bardzo trzeźwi mitografowie uznawali w tych gajach heneckich tylko symbole, „pojęcia o kraju bogów i o czasach rajskich”; przykład litewski poucza zaś dostatecznie, że podanie to, jak tyle innych, które najmylniej symbolicznie tłumaczą, należy rozumieć dosłownie, o prawdziwych gajach i zwierzętach, nie o jakimś raju i towarzyszach Adama; przesada w podaniu naturalnie razić nie może. Badania mitologiczne byłyby już od dawna o wiele głębiej dotarły, gdyby mania symbolizowania wszelkich szczegółów, i dziś jeszcze nie wykorzeniona, nie odwracała ich na manowce.\n-- Aleksander Brückner "Starożytna Litwa"'
        msg = message.MessageChallengeSolution(solution=solution)
        expected = {
            'SOLUTION': solution,
        }
        self.assertEquals(expected, msg.dict_repr())

    def test_no_payload_messages(self):
        for message_class in (
                message.MessagePing,
                message.MessagePong,
                message.MessageGetPeers,
                message.MessageGetTasks,
                message.MessageGetResourcePeers,
                ):
            msg = message_class()
            expected = {}
            self.assertEquals(expected, msg.dict_repr())

    def test_list_messages(self):
        for message_class, key in (
                (message.MessagePeers, 'PEERS'),
                (message.MessageTasks, 'TASKS'),
                (message.MessageResourcePeers, 'RESOURCE_PEERS'),
                ):
            msg = message_class()
            expected = {
                key: [],
            }
            self.assertEquals(expected, msg.dict_repr())

    def test_int_messages(self):
        for message_class, param_name, key in (
                    (message.MessageDisconnect, 'reason', 'DISCONNECT_REASON'),
                    (message.MessageDegree, 'degree', 'DEGREE'),
                ):
            value = random.randint(-10**10, 10**10)
            msg = message_class(**{param_name: value})
            expected = {
                key: value,
            }
            self.assertEquals(expected, msg.dict_repr())

    def test_message_remove_task(self):
        task_id = 'test-{}'.format(uuid.uuid4())
        msg = message.MessageRemoveTask(task_id=task_id)
        expected = {
            'REMOVE_TASK': task_id,
        }
        self.assertEquals(expected, msg.dict_repr())
