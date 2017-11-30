# -*- encoding: utf-8 -*-

from copy import copy
import inspect
import os
import random
import time
import unittest
import unittest.mock as mock
import uuid

from golem_messages import message

from golem.core.common import to_unicode
from golem.network.transport.tcpnetwork import BasicProtocol
from golem.task.taskbase import ResultType


class FailingMessage(message.Message):
    TYPE = -1

    def __init__(self, *args, **kwargs):
        message.Message.__init__(self, *args, **kwargs)

    def slots(self):
        raise Exception()


fake_sign = lambda x: b'\000'*65
fake_decrypt = lambda x: x


class TestMessages(unittest.TestCase):
    def setUp(self):
        random.seed()
        super(TestMessages, self).setUp()
        self.protocol = BasicProtocol()

    def test_message_want_to_compute_task(self):
        node_id = 'test-ni-{}'.format(uuid.uuid4())
        task_id = 'test-ti-{}'.format(uuid.uuid4())
        perf_index = random.random() * 1000
        price = random.random() * 1000
        max_resource_size = random.randint(1, 2**10)
        max_memory_size = random.randint(1, 2**10)
        num_cores = random.randint(1, 2**5)
        msg = message.MessageWantToComputeTask(
            node_name=node_id,
            task_id=task_id,
            perf_index=perf_index,
            price=price,
            max_resource_size=max_resource_size,
            max_memory_size=max_memory_size,
            num_cores=num_cores)
        expected = [
            ['node_name', node_id],
            ['task_id', task_id],
            ['perf_index', perf_index],
            ['max_resource_size', max_resource_size],
            ['max_memory_size', max_memory_size],
            ['num_cores', num_cores],
            ['price', price],
        ]
        self.assertEqual(expected, msg.slots())

    def test_message_report_computed_task(self):
        m = message.MessageReportComputedTask()
        self.assertIsInstance(m, message.MessageReportComputedTask)
        m = message.MessageReportComputedTask("xxyyzz", ResultType.DATA, 12034, "ABC", "10.10.10.1", 1023, "KEY_ID", "NODE", "ETH", {})
        self.assertEqual(m.subtask_id, "xxyyzz")
        self.assertEqual(m.result_type, ResultType.DATA)
        self.assertEqual(m.extra_data, {})
        self.assertEqual(m.computation_time, 12034)
        self.assertEqual(m.node_name, "ABC")
        self.assertEqual(m.address, "10.10.10.1")
        self.assertEqual(m.port, 1023)
        self.assertEqual(m.key_id, "KEY_ID")
        self.assertEqual(m.eth_account, "ETH")
        self.assertEqual(m.node_info, "NODE")
        self.assertEqual(m.TYPE, message.MessageReportComputedTask.TYPE)
        slots = m.slots()
        m2 = message.MessageReportComputedTask(slots=slots)
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
        assert m.serialize(fake_sign)

        m = FailingMessage()
        serialized = None

        try:
            serialized = m.serialize(fake_sign)
        except:
            pass
        assert not serialized
        assert not message.Message.deserialize(None, fake_decrypt)

    def test_unicode(self):
        source = str("test string")
        result = to_unicode(source)
        assert result is source

        source = "\xd0\xd1\xd2\xd3"
        result = to_unicode(source)
        assert result is source

        source = "test string"
        result = to_unicode(source)
        assert type(result) is str
        assert result == source

        source = None
        result = to_unicode(source)
        assert result is None

    @mock.patch('golem_messages.message.verify_time')
    def test_timestamp_and_timezones(self, vft_mock):
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
        self.protocol.db.append_len_prefixed_bytes(m.serialize(fake_sign))
        set_tz('US/Eastern')
        msgs = self.protocol._data_to_messages()
        assert len(msgs) == 1
        newyork_time = time.localtime(msgs[0].timestamp)
        assert warsaw_time != newyork_time
        assert time.gmtime(epoch_t) == time.gmtime(msgs[0].timestamp)

    def test_decrypt_and_deserialize(self):
        db = self.protocol.db
        n_messages = 10

        def serialize_messages(_b):
            for m in [message.MessageRandVal() for _ in range(0, n_messages)]:
                db.append_len_prefixed_bytes(m.serialize(fake_sign))

        serialize_messages(db)
        self.assertEqual(len(self.protocol._data_to_messages()), n_messages)

        patch_method = 'golem_messages.message.Message' \
                       '.deserialize'
        with mock.patch(patch_method, side_effect=lambda *_: None):
            serialize_messages(db)
            assert len(self.protocol._data_to_messages()) == 0

        def raise_assertion(*_):
            raise AssertionError()

        def raise_error(*_):
            raise Exception()

        serialize_messages(db)

        result = self.protocol._data_to_messages()
        assert len(result) == n_messages
        assert all(not m.encrypted for m in result)

        result = self.protocol._data_to_messages()
        assert len(result) == 0

    def test_message_randval(self):
        rand_val = random.random()
        msg = message.MessageRandVal(rand_val=rand_val)
        expected = [
            ['rand_val', rand_val],
        ]
        self.assertEqual(expected, msg.slots())

    def test_message_challenge_solution(self):
        solution = 'O gajach świętych, z których i drew zwalonych wichrem uprzątnąć się nie godziło, opowiada Długosz (XIII, 160), że świętymi były i zwierzęta chroniące się w nich, tak iż przez ciągły ów zwyczaj czworonożne i ptactwo tych lasów, jakby domowe jakie, nie stroniło od ludzi. Skoro zważymy, że dla Litwina gaje takie były rzeczywiście nietykalnymi, że sam Mindowg nie ważył się w nie wchodzić lub różdżkę w nich ułamać, zrozumiemy to podanie. Toż samo donosi w starożytności Strabon o Henetach: były u nich dwa gaje, Hery i Artemidy, „w gajach tych ułaskawiły się zwierzęta i jelenie z wilkami się kupiły; gdy się ludzie zbliżali i dotykali ich, nie uciekały; skoro gonione od psów tu się schroniły, ustawała pogoń”. I bardzo trzeźwi mitografowie uznawali w tych gajach heneckich tylko symbole, „pojęcia o kraju bogów i o czasach rajskich”; przykład litewski poucza zaś dostatecznie, że podanie to, jak tyle innych, które najmylniej symbolicznie tłumaczą, należy rozumieć dosłownie, o prawdziwych gajach i zwierzętach, nie o jakimś raju i towarzyszach Adama; przesada w podaniu naturalnie razić nie może. Badania mitologiczne byłyby już od dawna o wiele głębiej dotarły, gdyby mania symbolizowania wszelkich szczegółów, i dziś jeszcze nie wykorzeniona, nie odwracała ich na manowce.\n-- Aleksander Brückner "Starożytna Litwa"'
        msg = message.MessageChallengeSolution(solution=solution)
        expected = [
            ['solution', solution],
        ]
        self.assertEqual(expected, msg.slots())

    def test_no_payload_messages(self):
        for message_class in (
                message.MessagePing,
                message.MessagePong,
                message.MessageGetPeers,
                message.MessageGetTasks,
                message.MessageGetResourcePeers,
                message.MessageStopGossip,
                message.MessageWaitingForResults,
                ):
            msg = message_class()
            expected = []
            self.assertEqual(expected, msg.slots())

    def test_list_messages(self):
        for message_class, key in (
                (message.MessagePeers, 'peers'),
                (message.MessageTasks, 'tasks'),
                (message.MessageResourcePeers, 'resource_peers'),
                (message.MessageGossip, 'gossip'),
                ):
            msg = message_class()
            expected = [
                [key, []]
            ]
            self.assertEqual(expected, msg.slots())

    def test_int_messages(self):
        for message_class, key in (
                    (message.MessageDisconnect, 'reason'),
                    (message.MessageDegree, 'degree'),
                ):
            value = random.randint(-10**10, 10**10)
            msg = message_class(**{key: value})
            expected = [
                [key, value]
            ]
            self.assertEqual(expected, msg.slots())

    def test_uuid_messages(self):
        for message_class, key in (
                (message.MessageRemoveTask, 'task_id',),
                (message.MessageFindNode, 'node_key_id'),
                (message.MessageGetTaskResult, 'subtask_id'),
                (message.MessageStartSessionResponse, 'conn_id'),
                (message.MessageHasResource, 'resource'),
                (message.MessageWantsResource, 'resource'),
                (message.MessagePullResource, 'resource'),
                ):
            value = 'test-{}'.format(uuid.uuid4())
            msg = message_class(**{key: value})
            expected = [
                [key, value]
            ]
            self.assertEqual(expected, msg.slots())

    def test_message_loc_rank(self):
        node_id = 'test-{}'.format(uuid.uuid4())
        loc_rank = random.randint(-10**10, 10**10)
        msg = message.MessageLocRank(node_id=node_id, loc_rank=loc_rank)
        expected = [
            ['node_id', node_id],
            ['loc_rank', loc_rank]
        ]
        self.assertEqual(expected, msg.slots())

    def test_message_want_to_start_task_session(self):
        node_info = 'test-ni-{}'.format(uuid.uuid4())
        conn_id = 'test-ci-{}'.format(uuid.uuid4())
        super_node_info = 'test-sni-{}'.format(uuid.uuid4())
        msg = message.MessageWantToStartTaskSession(node_info=node_info, conn_id=conn_id, super_node_info=super_node_info)
        expected = [
            ['node_info', node_info],
            ['conn_id', conn_id],
            ['super_node_info', super_node_info],
        ]
        self.assertEqual(expected, msg.slots())

    def test_message_set_task_session(self):
        key_id = 'test-ki-{}'.format(uuid.uuid4())
        node_info = 'test-ni-{}'.format(uuid.uuid4())
        conn_id = 'test-ci-{}'.format(uuid.uuid4())
        super_node_info = 'test-sni-{}'.format(uuid.uuid4())
        msg = message.MessageSetTaskSession(key_id=key_id, node_info=node_info, conn_id=conn_id, super_node_info=super_node_info)
        expected = [
            ['key_id', key_id],
            ['node_info', node_info],
            ['conn_id', conn_id],
            ['super_node_info', super_node_info],
        ]
        self.assertEqual(expected, msg.slots())

    def test_message_get_resource(self):
        task_id = 'test-ti-{}'.format(uuid.uuid4())
        resource_header = 'test-rh-{}'.format(uuid.uuid4())
        msg = message.MessageGetResource(task_id=task_id, resource_header=resource_header)
        expected = [
            ['task_id', task_id],
            ['resource_header', resource_header],
        ]
        self.assertEqual(expected, msg.slots())

    def test_message_delta_parts(self):
        task_id = 'test-ti-{}'.format(uuid.uuid4())
        delta_header = 'test-dh-{}'.format(uuid.uuid4())
        parts = ['test-p{}-{}'.format(x, uuid.uuid4()) for x in range(10)]
        node_name = 'test-nn-{}'.format(uuid.uuid4())
        node_info = 'test-ni-{}'.format(uuid.uuid4())
        address = '8.8.8.8'
        port = random.randint(0, 2**16) + 1
        msg = message.MessageDeltaParts(
            task_id=task_id,
            delta_header=delta_header,
            parts=parts,
            node_name=node_name,
            node_info=node_info,
            address=address,
            port=port)
        expected = [
            ['task_id', task_id],
            ['delta_header', delta_header],
            ['parts', parts],
            ['node_name', node_name],
            ['address', address],
            ['port', port],
            ['node_info', node_info],
        ]
        self.assertEqual(expected, msg.slots())

    def test_message_task_failure(self):
        subtask_id = 'test-si-{}'.format(uuid.uuid4())
        err = 'Przesąd ten istnieje po dziś dzień u Mordwy, lecz już tylko symbol tego pozostał, co niegdyś dziki Fin w istocie tworzył.'

        msg = message.MessageTaskFailure(subtask_id=subtask_id, err=err)
        expected = [
            ['subtask_id', subtask_id],
            ['err', err],
        ]
        self.assertEqual(expected, msg.slots())

    def test_message_cannot_compute_task(self):
        subtask_id = 'test-si-{}'.format(uuid.uuid4())
        reason = "Opowiada Hieronim praski o osobliwszej czci, jaką w głębi Litwy cieszył się żelazny młot niezwykłej wielkości; „znaki zodiaka” rozbiły nim wieżę, w której potężny król słońce więził; należy się więc cześć narzędziu, co nam światło odzyskało. Już Mannhardt zwrócił uwagę na kult młotów (kamiennych) na północy; młoty „Tora” (pioruna) wyrabiano w Skandynawii dla czarów jeszcze w nowszych czasach; znajdujemy po grobach srebrne młoteczki jako amulety; hr. Tyszkiewicz opowiadał, jak wysoko chłop litewski cenił własności „kopalnego” młota (zeskrobany proszek z wodą przeciw chorobom służył itd.)."
        msg = message.MessageCannotComputeTask(subtask_id=subtask_id, reason=reason)
        expected = [
            ['reason', reason],
            ['subtask_id', subtask_id],
        ]
        self.assertEqual(expected, msg.slots())

    def test_message_push(self):
        resource = 'test-r-{}'.format(uuid.uuid4())
        copies = random.randint(-10**10, 10**10)
        msg = message.MessagePushResource(resource=resource, copies=copies)
        expected = [
            ['resource', resource],
            ['copies', copies],
        ]
        self.assertEqual(expected, msg.slots())

    def test_message_pull_answer(self):
        resource = 'test-r-{}'.format(uuid.uuid4())
        for has_resource in (True, False):
            msg = message.MessagePullAnswer(resource=resource, has_resource=has_resource)
            expected = [
                ['resource', resource],
                ['has_resource', has_resource],
            ]
            self.assertEqual(expected, msg.slots())

    def test_message_resource_list(self):
        resources = 'test-rs-{}'.format(uuid.uuid4())
        options = 'test-clientoptions-{}'.format(uuid.uuid4())
        msg = message.MessageResourceList(resources=resources, options=options)
        expected = [
            ['resources', resources],
            ['options', options],
        ]
        self.assertEqual(expected, msg.slots())

    def test_init_messages(self):
        def is_message_class(cls):
            return inspect.isclass(cls)\
                and issubclass(cls, message.Message)\
                and cls.TYPE is not None

        message_classes = inspect.getmembers(message, is_message_class)

        message_types = {}
        for _, message_class in message_classes:
            message_types[message_class.TYPE] = message_class

        message.init_messages()

        assert message_types == message.registered_message_types

    @mock.patch("golem_messages.message.MessageRandVal")
    def test_init_messages_error(self, mock_message_rand_val):
        copy_registered = copy(message.registered_message_types)
        message.registered_message_types = {}
        mock_message_rand_val.__name__ = "randvalmessage"
        mock_message_rand_val.TYPE = message.MessageHello.TYPE
        with self.assertRaises(RuntimeError):
            message.init_messages()
        message.registered_message_types = copy_registered

    def test_slots(self):
        message.init_messages()

        for cls in message.registered_message_types.values():
            # only __slots__ can be present in objects
            self.assertFalse(hasattr(cls(), '__dict__'), "{} instance has __dict__".format(cls))
            assert not hasattr(cls.__new__(cls), '__dict__')
            # slots are properly set in class definition
            assert len(cls.__slots__) >= len(message.Message.__slots__)
