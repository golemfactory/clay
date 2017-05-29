# -*- encoding: utf-8 -*-

from copy import copy
import os
import random
import time
import unittest
import uuid

from golem.core.common import to_unicode
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
        expected = {
            'NODE_NAME': node_id,
            'TASK_ID': task_id,
            'PERF_INDEX': perf_index,
            'MAX_RES': max_resource_size,
            'MAX_MEM': max_memory_size,
            'NUM_CORES': num_cores,
            'PRICE': price,
        }
        self.assertEquals(expected, msg.dict_repr())

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
        result = to_unicode(source)
        assert result is source

        source = "\xd0\xd1\xd2\xd3"
        result = to_unicode(source)
        assert result is source

        source = "test string"
        result = to_unicode(source)
        assert type(result) is unicode
        assert result is not source
        assert result == source

        source = None
        result = to_unicode(source)
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
                message.MessageStopGossip,
                message.MessageBeingMiddlemanAccepted,
                message.MessageMiddlemanAccepted,
                message.MessageMiddlemanReady,
                message.MessageNatPunchFailure,
                message.MessageWaitingForResults,
                ):
            msg = message_class()
            expected = {}
            self.assertEquals(expected, msg.dict_repr())

    def test_list_messages(self):
        for message_class, key in (
                (message.MessagePeers, 'PEERS'),
                (message.MessageTasks, 'TASKS'),
                (message.MessageResourcePeers, 'RESOURCE_PEERS'),
                (message.MessageGossip, 'GOSSIP'),
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
                    (message.MessageWaitForNatTraverse, 'port', 'PORT'),
                ):
            value = random.randint(-10**10, 10**10)
            msg = message_class(**{param_name: value})
            expected = {
                key: value,
            }
            self.assertEquals(expected, msg.dict_repr())

    def test_uuid_messages(self):
        for message_class, param_name, key in (
                (message.MessageRemoveTask, 'task_id', 'REMOVE_TASK'),
                (message.MessageFindNode, 'node_key_id', 'NODE_KEY_ID'),
                (message.MessageNatTraverseFailure, 'conn_id', 'CONN_ID'),
                (message.MessageGetTaskResult, 'subtask_id', 'SUB_TASK_ID'),
                (message.MessageStartSessionResponse, 'conn_id', 'CONN_ID'),
                (message.MessageHasResource, 'resource', 'resource'),
                (message.MessageWantsResource, 'resource', 'resource'),
                (message.MessagePullResource, 'resource', 'resource'),
                ):
            value = 'test-{}'.format(uuid.uuid4())
            msg = message_class(**{param_name: value})
            expected = {
                key: value,
            }
            self.assertEquals(expected, msg.dict_repr())

    def test_message_loc_rank(self):
        node_id = 'test-{}'.format(uuid.uuid4())
        loc_rank = random.randint(-10**10, 10**10)
        msg = message.MessageLocRank(node_id=node_id, loc_rank=loc_rank)
        expected = {
            'LOC_RANK': loc_rank,
            'NODE_ID': node_id,
        }
        self.assertEquals(expected, msg.dict_repr())

    def test_message_want_to_start_task_session(self):
        node_info = 'test-ni-{}'.format(uuid.uuid4())
        conn_id = 'test-ci-{}'.format(uuid.uuid4())
        super_node_info = 'test-sni-{}'.format(uuid.uuid4())
        msg = message.MessageWantToStartTaskSession(node_info=node_info, conn_id=conn_id, super_node_info=super_node_info)
        expected = {
            'NODE_INFO': node_info,
            'CONN_ID': conn_id,
            'SUPER_NODE_INFO': super_node_info,
        }
        self.assertEquals(expected, msg.dict_repr())

    def test_message_set_task_session(self):
        key_id = 'test-ki-{}'.format(uuid.uuid4())
        node_info = 'test-ni-{}'.format(uuid.uuid4())
        conn_id = 'test-ci-{}'.format(uuid.uuid4())
        super_node_info = 'test-sni-{}'.format(uuid.uuid4())
        msg = message.MessageSetTaskSession(key_id=key_id, node_info=node_info, conn_id=conn_id, super_node_info=super_node_info)
        expected = {
            'KEY_ID': key_id,
            'NODE_INFO': node_info,
            'CONN_ID': conn_id,
            'SUPER_NODE_INFO': super_node_info,
        }
        self.assertEquals(expected, msg.dict_repr())

    def test_message_nat_hole(self):
        key_id = 'test-ki-{}'.format(uuid.uuid4())
        conn_id = 'test-ci-{}'.format(uuid.uuid4())
        address = '8.8.8.8'
        port = random.randint(0, 2**16) + 1
        msg = message.MessageNatHole(key_id=key_id, conn_id=conn_id, address=address, port=port)
        expected = {
            'KEY_ID': key_id,
            'ADDR': address,
            'CONN_ID': conn_id,
            'PORT': port,
        }
        self.assertEquals(expected, msg.dict_repr())

    def test_message_inform_about_nat_traverse_failure(self):
        key_id = 'test-ki-{}'.format(uuid.uuid4())
        conn_id = 'test-ci-{}'.format(uuid.uuid4())
        msg = message.MessageInformAboutNatTraverseFailure(key_id=key_id, conn_id=conn_id)
        expected = {
            'KEY_ID': key_id,
            'CONN_ID': conn_id,
        }
        self.assertEquals(expected, msg.dict_repr())

    def test_message_get_resource(self):
        task_id = 'test-ti-{}'.format(uuid.uuid4())
        resource_header = 'test-rh-{}'.format(uuid.uuid4())
        msg = message.MessageGetResource(task_id=task_id, resource_header=resource_header)
        expected = {
            'SUB_TASK_ID': task_id,
            'RESOURCE_HEADER': resource_header,
        }
        self.assertEquals(expected, msg.dict_repr())

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
        expected = {
            'TASK_ID': task_id,
            'DELTA_HEADER': delta_header,
            'PARTS': parts,
            'NODE_NAME': node_name,
            'ADDR': address,
            'PORT': port,
            'node info': node_info,
        }
        self.assertEquals(expected, msg.dict_repr())

    def test_message_task_failure(self):
        subtask_id = 'test-si-{}'.format(uuid.uuid4())
        err = u'Przesąd ten istnieje po dziś dzień u Mordwy, lecz już tylko symbol tego pozostał, co niegdyś dziki Fin w istocie tworzył.'

        msg = message.MessageTaskFailure(subtask_id=subtask_id, err=err)
        expected = {
            'SUBTASK_ID': subtask_id,
            'ERR': err,
        }
        self.assertEquals(expected, msg.dict_repr())

    def test_message_middleman(self):
        asking_node = 'test-an-{}'.format(uuid.uuid4())
        dest_node = 'test-dn-{}'.format(uuid.uuid4())
        ask_conn_id = 'test-aci-{}'.format(uuid.uuid4())
        msg = message.MessageMiddleman(asking_node=asking_node, dest_node=dest_node, ask_conn_id=ask_conn_id)
        expected = {
            'ASKING_NODE': asking_node,
            'DEST_NODE': dest_node,
            'ASK_CONN_ID': ask_conn_id,
        }
        self.assertEquals(expected, msg.dict_repr())

    def test_message_join_middleman_conn(self):
        key_id = 'test-ki-{}'.format(uuid.uuid4())
        dest_node = 'test-dn-{}'.format(uuid.uuid4())
        conn_id = 'test-ci-{}'.format(uuid.uuid4())
        msg = message.MessageJoinMiddlemanConn(key_id=key_id, conn_id=conn_id, dest_node_key_id=dest_node)
        expected = {
            'CONN_ID': conn_id,
            'KEY_ID': key_id,
            'DEST_NODE_KEY_ID': dest_node,
        }
        self.assertEquals(expected, msg.dict_repr())

    def test_message_nat_punch(self):
        asking_node = 'test-an-{}'.format(uuid.uuid4())
        dest_node = 'test-dn-{}'.format(uuid.uuid4())
        ask_conn_id = 'test-aci-{}'.format(uuid.uuid4())
        msg = message.MessageNatPunch(asking_node=asking_node, dest_node=dest_node, ask_conn_id=ask_conn_id)
        expected = {
            'ASKING_NODE': asking_node,
            'DEST_NODE': dest_node,
            'ASK_CONN_ID': ask_conn_id,
        }
        self.assertEquals(expected, msg.dict_repr())

    def test_message_cannot_compute_task(self):
        subtask_id = 'test-si-{}'.format(uuid.uuid4())
        reason = u"Opowiada Hieronim praski o osobliwszej czci, jaką w głębi Litwy cieszył się żelazny młot niezwykłej wielkości; „znaki zodiaka” rozbiły nim wieżę, w której potężny król słońce więził; należy się więc cześć narzędziu, co nam światło odzyskało. Już Mannhardt zwrócił uwagę na kult młotów (kamiennych) na północy; młoty „Tora” (pioruna) wyrabiano w Skandynawii dla czarów jeszcze w nowszych czasach; znajdujemy po grobach srebrne młoteczki jako amulety; hr. Tyszkiewicz opowiadał, jak wysoko chłop litewski cenił własności „kopalnego” młota (zeskrobany proszek z wodą przeciw chorobom służył itd.)."
        msg = message.MessageCannotComputeTask(subtask_id=subtask_id, reason=reason)
        expected = {
            'REASON': reason,
            'SUBTASK_ID': subtask_id,
        }
        self.assertEquals(expected, msg.dict_repr())

    def test_message_push(self):
        resource = 'test-r-{}'.format(uuid.uuid4())
        copies = random.randint(-10**10, 10**10)
        msg = message.MessagePushResource(resource=resource, copies=copies)
        expected = {
            'resource': resource,
            'copies': copies,
        }
        self.assertEquals(expected, msg.dict_repr())

    def test_message_pull_answer(self):
        resource = 'test-r-{}'.format(uuid.uuid4())
        for has_resource in (True, False):
            msg = message.MessagePullAnswer(resource=resource, has_resource=has_resource)
            expected = {
                'resource': resource,
                'has resource': has_resource,
            }
            self.assertEquals(expected, msg.dict_repr())

    def test_message_resource_list(self):
        resources = 'test-rs-{}'.format(uuid.uuid4())
        options = 'test-clientoptions-{}'.format(uuid.uuid4())
        msg = message.MessageResourceList(resources=resources, options=options)
        expected = {
            'resources': resources,
            'options': options,
        }
        self.assertEquals(expected, msg.dict_repr())

    @mock.patch("golem.network.transport.message.MessageRandVal")
    def test_init_messages_error(self, mock_message_rand_val):
        copy_registered = copy(message.Message.registered_message_types)
        message.Message.registered_message_types = dict()
        mock_message_rand_val.__name__ = "randvalmessage"
        mock_message_rand_val.TYPE = message.MessageHello.TYPE
        with self.assertRaises(RuntimeError):
            message.init_messages()
        message.Message.registered_message_types = copy_registered
