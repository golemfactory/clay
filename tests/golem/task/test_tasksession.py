# pylint: disable=too-many-lines, protected-access
import calendar
import datetime
import os
import pathlib
import pickle
import random
import time
import uuid
from unittest import TestCase
from unittest.mock import patch, ANY, Mock, MagicMock

from golem_messages import factories as msg_factories
from golem_messages import idgenerator
from golem_messages import message
from golem_messages import cryptography
from golem_messages.utils import encode_hex

from twisted.internet.defer import Deferred

import golem
from golem import model, testutils
from golem.core.databuffer import DataBuffer
from golem.core.keysauth import KeysAuth
from golem.core.variables import PROTOCOL_CONST
from golem.docker.environment import DockerEnvironment
from golem.docker.image import DockerImage
from golem.model import Actor
from golem.network import history
from golem.network.p2p.node import Node
from golem.network.transport.tcpnetwork import BasicProtocol
from golem.resource.client import ClientOptions
from golem.task import taskstate
from golem.task.taskbase import ResultType, TaskHeader
from golem.task.taskkeeper import CompTaskKeeper
from golem.task.tasksession import TaskSession, logger, get_task_message
from golem.tools.assertlogs import LogTestCase

from tests import factories
from tests.factories import p2p as p2p_factories
from tests.factories.task import taskbase as taskbase_factories


def fill_slots(msg):
    for slot in msg.__slots__:
        if hasattr(msg, slot):
            continue
        setattr(msg, slot, None)


class DockerEnvironmentMock(DockerEnvironment):
    DOCKER_IMAGE = ""
    DOCKER_TAG = ""
    ENV_ID = ""
    APP_DIR = ""
    SCRIPT_NAME = ""
    SHORT_DESCRIPTION = ""


class TestTaskSessionPep8(testutils.PEP8MixIn, TestCase):
    PEP8_FILES = ['golem/task/tasksession.py', ]


class ConcentMessageMixin():
    def assert_concent_cancel(self, mock_call, subtask_id, message_class_name):
        self.assertEqual(mock_call[0], subtask_id)
        self.assertEqual(mock_call[1], message_class_name)

    def assert_concent_submit(self, mock_call, subtask_id, message_class):
        self.assertEqual(mock_call[0], subtask_id)
        self.assertIsInstance(mock_call[1], message_class)


# pylint:disable=no-member
class TaskSessionTaskToComputeTest(TestCase):
    def setUp(self):
        self.requestor_keys = cryptography.ECCx(None)
        self.requestor_key = encode_hex(self.requestor_keys.raw_pubkey)
        self.provider_keys = cryptography.ECCx(None)
        self.provider_key = encode_hex(self.provider_keys.raw_pubkey)

        self.task_manager = Mock(tasks_states={}, tasks={})
        server = Mock(task_manager=self.task_manager)
        server.get_key_id = lambda: self.provider_key
        self.conn = Mock(server=server)
        self.use_concent = True
        self.task_id = uuid.uuid4().hex
        self.node_name = 'ABC'

    def _get_task_session(self):
        ts = TaskSession(self.conn)
        ts._is_peer_blocked = Mock(return_value=False)
        ts.verified = True
        ts.concent_service.enabled = self.use_concent
        ts.key_id = 'requestor key id'
        return ts

    def _get_requestor_tasksession(self, accept_provider=True):
        ts = self._get_task_session()
        ts.key_id = "provider key id"
        ts.can_be_not_encrypted.append(message.tasks.WantToComputeTask)
        ts.task_server.should_accept_provider.return_value = accept_provider
        ts.task_server.config_desc.max_price = 100
        ts.task_server.keys_auth._private_key = \
            self.requestor_keys.raw_privkey
        return ts

    def _get_task_parameters(self):
        return {
            'node_name': self.node_name,
            'task_id': self.task_id,
            'perf_index': 1030,
            'price': 30,
            'max_resource_size': 3,
            'max_memory_size': 1,
            'num_cores': 8,
        }

    def _get_wtct(self):
        return message.tasks.WantToComputeTask(
            concent_enabled=self.use_concent,
            **self._get_task_parameters()
        )

    def _fake_add_task(self):
        task_header = TaskHeader(
            task_id=self.task_id,
            environment='',
            task_owner=Node(
                key=self.requestor_key,
                node_name=self.node_name,
                pub_addr='10.10.10.10',
                pub_port=12345,
            )
        )
        self.task_manager.tasks[self.task_id] = Mock(header=task_header)

    def _set_task_state(self):
        task_state = taskstate.TaskState()
        task_state.package_hash = '667'
        task_state.package_size = 42
        self.conn.server.task_manager.tasks_states[self.task_id] = task_state
        return task_state

    def test_want_to_compute_task(self):
        ts = self._get_task_session()
        ts._handshake_required = Mock(return_value=False)
        params = self._get_task_parameters()
        ts.task_server.task_keeper.task_headers = task_headers = {}
        task_headers[params['task_id']] = taskbase_factories.TaskHeader()
        ts.concent_service.enabled = False
        ts.request_task(
            params['node_name'],
            params['task_id'],
            params['perf_index'],
            params['price'],
            params['max_resource_size'],
            params['max_memory_size'],
            params['num_cores']
        )
        ts.conn.send_message.assert_called_once()
        mt = ts.conn.send_message.call_args[0][0]
        self.assertIsInstance(mt, message.tasks.WantToComputeTask)
        self.assertEqual(mt.node_name, params['node_name'])
        self.assertEqual(mt.task_id, params['task_id'])
        self.assertEqual(mt.perf_index, params['perf_index'])
        self.assertEqual(mt.price, params['price'])
        self.assertEqual(mt.max_resource_size, params['max_resource_size'])
        self.assertEqual(mt.max_memory_size, params['max_memory_size'])
        self.assertEqual(mt.num_cores, params['num_cores'])
        self.assertEqual(mt.provider_public_key, self.provider_key)
        self.assertEqual(mt.provider_ethereum_public_key, self.provider_key)

    @patch('golem.network.history.MessageHistoryService.instance')
    def test_cannot_assign_task_provider_not_accepted(self, *_):
        mt = self._get_wtct()
        ts2 = self._get_requestor_tasksession(accept_provider=False)
        self._fake_add_task()

        ctd = message.tasks.ComputeTaskDef(
            task_type=message.tasks.TaskType.Blender.name,
            meta_parameters=msg_factories.tasks.BlenderScriptPackageFactory(),
            task_id=mt.task_id,
        )
        self._set_task_state()

        ts2.task_manager.get_next_subtask.return_value = ctd
        ts2.task_manager.should_wait_for_node.return_value = False
        ts2.task_server.should_accept_provider.return_value = False
        ts2.interpret(mt)
        ms = ts2.conn.send_message.call_args[0][0]
        self.assertIsInstance(ms, message.tasks.CannotAssignTask)
        self.assertEqual(ms.task_id, mt.task_id)

    @patch('golem.network.history.MessageHistoryService.instance')
    def test_cannot_assign_task_wrong_ctd(self, *_):
        mt = self._get_wtct()
        ts2 = self._get_requestor_tasksession()
        self._fake_add_task()

        self._set_task_state()

        ts2.task_manager.should_wait_for_node.return_value = False
        ts2.task_manager.check_next_subtask.return_value = False
        ts2.interpret(mt)
        ms = ts2.conn.send_message.call_args[0][0]
        self.assertIsInstance(ms, message.tasks.CannotAssignTask)
        self.assertEqual(ms.task_id, mt.task_id)

    def test_cannot_compute_task_computation_failure(self):
        ts2 = self._get_requestor_tasksession()
        ts2.task_manager.get_node_id_for_subtask.return_value = ts2.key_id
        ts2._react_to_cannot_compute_task(message.tasks.CannotComputeTask(
            reason=message.tasks.CannotComputeTask.REASON.WrongCTD,
            task_to_compute=None,
        ))
        assert ts2.task_manager.task_computation_failure.called

    def test_cannot_compute_task_bad_subtask_id(self):
        ts2 = self._get_requestor_tasksession()
        ts2.task_manager.task_computation_failure.called = False
        ts2.task_manager.get_node_id_for_subtask.return_value = "___"
        ts2._react_to_cannot_compute_task(message.tasks.CannotComputeTask(
            reason=message.tasks.CannotComputeTask.REASON.WrongCTD,
            task_to_compute=None,
        ))
        assert not ts2.task_manager.task_computation_failure.called

    @patch('golem.network.history.MessageHistoryService.instance')
    def test_request_task(self, *_):
        mt = self._get_wtct()
        ts2 = self._get_requestor_tasksession(accept_provider=True)
        self._fake_add_task()

        ctd = message.tasks.ComputeTaskDef(
            task_type=message.tasks.TaskType.Blender.name,
            meta_parameters=msg_factories.tasks.BlenderScriptPackageFactory(),
            task_id=mt.task_id,
        )
        task_state = self._set_task_state()

        ts2.task_manager.get_next_subtask.return_value = ctd
        ts2.task_manager.should_wait_for_node.return_value = False
        ts2.interpret(mt)
        ms = ts2.conn.send_message.call_args[0][0]
        self.assertIsInstance(ms, message.tasks.TaskToCompute)
        expected = [
            ['requestor_id', self.requestor_key],
            ['provider_id', ts2.key_id],
            ['requestor_public_key', self.requestor_key],
            ['requestor_ethereum_public_key', self.requestor_key],
            ['compute_task_def', ctd],
            ['want_to_compute_task', mt],
            ['package_hash', 'sha1:' + task_state.package_hash],
            ['concent_enabled', self.use_concent],
            ['price', 0],
            ['size', task_state.package_size],
        ]
        self.assertCountEqual(ms.slots(), expected)

    def test_task_to_compute_eth_signature(self):
        wtct = self._get_wtct()
        ts2 = self._get_requestor_tasksession(accept_provider=True)
        self._fake_add_task()

        ctd = message.tasks.ComputeTaskDef(
            meta_parameters=msg_factories.tasks.BlenderScriptPackageFactory(),
            task_type=message.tasks.TaskType.Blender.name,
            task_id=wtct.task_id,
        )
        self._set_task_state()

        ts2.task_manager.get_next_subtask.return_value = ctd
        ts2.task_manager.should_wait_for_node.return_value = False
        ts2.interpret(wtct)
        ttc = ts2.conn.send_message.call_args[0][0]
        self.assertIsInstance(ttc, message.tasks.TaskToCompute)
        self.assertEqual(ttc.requestor_ethereum_public_key, self.requestor_key)
        self.assertTrue(ttc.verify_ethsig())

# pylint:enable=no-member


class TestTaskSession(ConcentMessageMixin, LogTestCase,
                      testutils.TempDirFixture):

    def setUp(self):
        super(TestTaskSession, self).setUp()
        random.seed()
        self.task_session = TaskSession(Mock())
        self.task_session.key_id = 'unittest_key_id'

    @patch('golem.task.tasksession.TaskSession.send')
    def test_hello(self, send_mock):
        self.task_session.conn.server.get_key_id.return_value = key_id = \
            'key id%d' % (random.random() * 1000,)
        self.task_session.send_hello()
        expected = [
            ['rand_val', self.task_session.rand_val],
            ['proto_id', PROTOCOL_CONST.ID],
            ['node_name', None],
            ['node_info', None],
            ['port', None],
            ['client_ver', golem.__version__],
            ['client_key_id', key_id],
            ['solve_challenge', None],
            ['challenge', None],
            ['difficulty', None],
            ['metadata', None],
        ]
        msg = send_mock.call_args[0][0]
        self.assertCountEqual(msg.slots(), expected)

    @patch(
        'golem.network.history.MessageHistoryService.get_sync_as_message',
    )
    @patch(
        'golem.network.history.add',
    )
    def test_send_report_computed_task(self, add_mock, get_mock):
        ts = self.task_session
        ts.verified = True
        ts.task_server.get_node_name.return_value = "ABC"
        wtr = factories.taskserver.WaitingTaskResultFactory()

        ttc = msg_factories.tasks.TaskToComputeFactory(
            task_id=wtr.task_id,
            subtask_id=wtr.subtask_id,
            compute_task_def__deadline=calendar.timegm(time.gmtime()) + 3600,
        )
        get_mock.return_value = ttc
        ts.task_server.get_key_id.return_value = 'key id'
        ts.send_report_computed_task(
            wtr, wtr.owner.pub_addr, wtr.owner.pub_port, wtr.owner)

        rct: message.tasks.ReportComputedTask = \
            ts.conn.send_message.call_args[0][0]
        self.assertIsInstance(rct, message.tasks.ReportComputedTask)
        self.assertEqual(rct.subtask_id, wtr.subtask_id)
        self.assertEqual(rct.result_type, ResultType.DATA)
        self.assertEqual(rct.node_name, "ABC")
        self.assertEqual(rct.address, wtr.owner.pub_addr)
        self.assertEqual(rct.port, wtr.owner.pub_port)
        self.assertEqual(rct.extra_data, [])
        self.assertEqual(rct.node_info, wtr.owner.to_dict())
        self.assertEqual(rct.package_hash, 'sha1:' + wtr.package_sha1)
        self.assertEqual(rct.multihash, wtr.result_hash)
        self.assertEqual(rct.secret, wtr.result_secret)

        add_mock.assert_called_once_with(
            msg=rct,
            node_id=ts.key_id,
            local_role=Actor.Provider,
            remote_role=Actor.Requestor,
        )

        ts2 = TaskSession(Mock())
        ts2.verified = True
        ts2.key_id = "DEF"
        ts2.can_be_not_encrypted.append(rct.__class__)
        ts2.task_manager.subtask2task_mapping = {wtr.subtask_id: wtr.task_id}
        task_state = taskstate.TaskState()
        task_state.subtask_states[wtr.subtask_id] = taskstate.SubtaskState()
        task_state.subtask_states[wtr.subtask_id].deadline = \
            calendar.timegm(time.gmtime()) + 3600
        ts2.task_manager.tasks_states = {
            wtr.task_id: task_state,
        }
        ts2.task_manager.get_node_id_for_subtask.return_value = "DEF"
        get_mock.side_effect = history.MessageNotFound

        with patch(
            'golem.network.concent.helpers.process_report_computed_task',
            return_value=msg_factories.tasks.AckReportComputedTaskFactory()
        ):
            ts2.interpret(rct)
        wtr.result_type = "UNKNOWN"
        with self.assertLogs(logger, level="ERROR"):
            ts.send_report_computed_task(
                wtr, wtr.owner.pub_addr, wtr.owner.pub_port, wtr.owner)

    def test_react_to_hello_protocol_version(self):
        # given
        conn = MagicMock()
        ts = TaskSession(conn)
        ts.task_server = Mock()
        ts.task_server.config_desc = Mock()
        ts.task_server.config_desc.key_difficulty = 0
        ts.disconnect = Mock()
        ts.send = Mock()

        key_id = 'deadbeef'
        peer_info = MagicMock()
        peer_info.key = key_id
        msg = message.base.Hello(
            port=1, node_name='node2', client_key_id=key_id,
            node_info=peer_info, proto_id=-1)
        fill_slots(msg)

        # when
        with self.assertLogs(logger, level='INFO'):
            ts._react_to_hello(msg)

        # then
        ts.disconnect.assert_called_with(
            message.base.Disconnect.REASON.ProtocolVersion)

        # re-given
        msg.proto_id = PROTOCOL_CONST.ID

        # re-when
        with self.assertNoLogs(logger, level='INFO'):
            ts._react_to_hello(msg)

        # re-then
        self.assertTrue(ts.send.called)

    def test_react_to_hello_key_not_difficult(self):
        # given
        conn = MagicMock()
        ts = TaskSession(conn)
        ts.task_server = Mock()
        ts.task_server.config_desc = Mock()
        ts.task_server.config_desc.key_difficulty = 80
        ts.disconnect = Mock()
        ts.send = Mock()

        key_id = 'deadbeef'
        peer_info = MagicMock()
        peer_info.key = key_id
        msg = message.base.Hello(
            port=1, node_name='node2', client_key_id=key_id,
            node_info=peer_info, proto_id=PROTOCOL_CONST.ID)
        fill_slots(msg)

        # when
        with self.assertLogs(logger, level='INFO'):
            ts._react_to_hello(msg)

        # then
        ts.disconnect.assert_called_with(
            message.base.Disconnect.REASON.KeyNotDifficult)

    def test_react_to_hello_key_difficult(self):
        # given
        difficulty = 4
        conn = MagicMock()
        ts = TaskSession(conn)
        ts.task_server = Mock()
        ts.task_server.config_desc = Mock()
        ts.task_server.config_desc.key_difficulty = difficulty
        ts.disconnect = Mock()
        ts.send = Mock()

        ka = KeysAuth(datadir=self.path, difficulty=difficulty,
                      private_key_name='prv', password='')
        peer_info = MagicMock()
        peer_info.key = ka.key_id
        msg = message.base.Hello(
            port=1, node_name='node2', client_key_id=ka.key_id,
            node_info=peer_info, proto_id=PROTOCOL_CONST.ID)
        fill_slots(msg)

        # when
        with self.assertNoLogs(logger, level='INFO'):
            ts._react_to_hello(msg)
        # then
        self.assertTrue(ts.send.called)

    @patch('golem.task.tasksession.get_task_message')
    def test_result_received(self, get_msg_mock):
        conn = Mock()
        ts = TaskSession(conn)
        ts.task_server = Mock()
        ts.task_manager = Mock()
        ts.task_manager.verify_subtask.return_value = True
        subtask_id = "xxyyzz"
        get_msg_mock.return_value = msg_factories \
            .tasks.ReportComputedTaskFactory(
                subtask_id=subtask_id,
            )

        def finished():
            if not ts.task_manager.verify_subtask(subtask_id):
                ts._reject_subtask_result(subtask_id, '')
                ts.dropped()
                return

            payment = ts.task_server.accept_result(
                subtask_id,
                'key_id',
                'eth_address',
            )
            ts.send(msg_factories.tasks.SubtaskResultsAcceptedFactory(
                task_to_compute__compute_task_def__subtask_id=subtask_id,
                payment_ts=payment.processed_ts))
            ts.dropped()

        extra_data = dict(
            # the result is explicitly serialized using cPickle
            result=pickle.dumps({'stdout': 'xyz'}),
            result_type=None,
            subtask_id=subtask_id,
        )

        ts.result_received(extra_data)

        self.assertTrue(ts.msgs_to_send)
        self.assertIsInstance(ts.msgs_to_send[0],
                              message.tasks.SubtaskResultsRejected)
        self.assertTrue(conn.close.called)

        extra_data.update(dict(
            result_type=ResultType.DATA,
        ))
        conn.close.called = False
        ts.msgs_to_send = []

        ts.task_manager.computed_task_received = Mock(
            side_effect=finished(),
        )
        ts.result_received(extra_data)

        self.assertTrue(ts.msgs_to_send)
        sra = ts.msgs_to_send[0]
        self.assertIsInstance(sra, message.tasks.SubtaskResultsAccepted)

        conn.close.assert_called()

        extra_data.update(dict(
            subtask_id=None,
        ))
        conn.close.called = False
        ts.msgs_to_send = []

        ts.result_received(extra_data)

        assert not ts.msgs_to_send
        assert conn.close.called

    def _get_srr(self, key2=None, concent=False):
        key1 = 'known'
        key2 = key2 or key1
        srr = msg_factories.tasks.SubtaskResultsRejectedFactory(
            report_computed_task__task_to_compute__concent_enabled=concent
        )
        ctk = self.task_session.task_manager.comp_task_keeper
        ctk.get_node_for_task_id.return_value = key1
        self.task_session.key_id = key2
        return srr

    def __call_react_to_srr(self, srr):
        with patch('golem.task.tasksession.TaskSession.dropped') as dropped:
            self.task_session._react_to_subtask_results_rejected(srr)
        dropped.assert_called_once_with()

    def test_result_rejected(self):
        srr = self._get_srr()
        self.__call_react_to_srr(srr)
        self.task_session.task_server.subtask_rejected.assert_called_once_with(
            sender_node_id=self.task_session.key_id,
            subtask_id=srr.report_computed_task.subtask_id,  # noqa pylint:disable=no-member
        )

    def test_result_rejected_with_wrong_key(self):
        srr = self._get_srr(key2='notmine')
        self.__call_react_to_srr(srr)
        self.task_session.task_server.subtask_rejected.assert_not_called()

    def test_result_rejected_with_concent(self):
        srr = self._get_srr(concent=True)
        self.task_session.task_server.client.funds_locker\
            .sum_locks.return_value = (0,)

        def concent_deposit(**_):
            result = Deferred()
            result.callback(None)
            return result

        self.task_session.task_server.client.transaction_system\
            .concent_deposit.side_effect = concent_deposit
        self.__call_react_to_srr(srr)
        stm = self.task_session.concent_service.submit_task_message
        stm.assert_called()
        kwargs = stm.call_args_list[0][1]
        self.assertEqual(kwargs['subtask_id'], srr.subtask_id)
        self.assertIsInstance(kwargs['msg'],
                              message.concents.SubtaskResultsVerify)
        self.assertEqual(kwargs['msg'].subtask_results_rejected, srr)

    # pylint: disable=too-many-statements
    def test_react_to_task_to_compute(self):
        conn = Mock()
        ts = TaskSession(conn)
        ts.key_id = "KEY_ID"
        ts.task_manager = MagicMock()
        ts.task_computer = Mock()
        ts.task_server = Mock()
        ts.concent_service.enabled = False
        ts.send = Mock()

        env = Mock()
        env.docker_images = [DockerImage("dockerix/xii", tag="323")]
        env.allow_custom_main_program_file = False
        env.get_source_code.return_value = None
        ts.task_server.get_environment_by_id.return_value = env

        keys = cryptography.ECCx(None)
        ts.task_server.keys_auth.ecc.raw_pubkey = keys.raw_pubkey

        reasons = message.tasks.CannotComputeTask.REASON

        def __reset_mocks():
            ts.task_manager.reset_mock()
            ts.task_computer.reset_mock()
            conn.reset_mock()

        # msg.ctd is None -> failure
        msg = msg_factories.tasks.TaskToComputeFactory(compute_task_def=None)
        msg.want_to_compute_task.sign_message(keys.raw_privkey)  # pylint: disable=no-member
        ts._react_to_task_to_compute(msg)
        ts.task_server.add_task_session.assert_not_called()
        ts.task_computer.task_given.assert_not_called()
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.send.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        # No source code in the local environment -> failure
        __reset_mocks()
        header = ts.task_manager.comp_task_keeper.get_task_header()
        header.task_owner.key = 'KEY_ID'
        header.task_owner.pub_addr = '10.10.10.10'
        header.task_owner.pub_port = 1112

        ctd = message.tasks.ComputeTaskDef(
            task_type=message.tasks.TaskType.Blender.name,  # noqa pylint:disable=no-member
            meta_parameters=msg_factories.tasks.BlenderScriptPackageFactory()
        )
        ctd['docker_images'] = [
            DockerImage("dockerix/xiii", tag="323").to_dict(),
        ]

        def _prepare_and_react(compute_task_def):
            msg = msg_factories.tasks.TaskToComputeFactory(
                compute_task_def=compute_task_def,
            )
            msg.want_to_compute_task.provider_public_key = encode_hex(
                keys.raw_pubkey)
            msg.want_to_compute_task.sign_message(keys.raw_privkey)  # pylint: disable=no-member
            ts.task_server.task_keeper.task_headers = {
                msg.task_id: MagicMock(),
            }
            ts.task_server.task_keeper\
                .task_headers[msg.task_id].subtasks_count = 10
            ts.task_server.client.transaction_system.get_available_gnt\
                .return_value = msg.price * 10
            ts._react_to_task_to_compute(msg)
            return msg

        _prepare_and_react(ctd)
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        # Source code from local environment -> proper execution
        __reset_mocks()
        env.get_source_code.return_value = "print 'Hello world'"
        msg = _prepare_and_react(ctd)
        ts.task_manager.comp_task_keeper.receive_subtask.assert_called_with(msg)
        ts.task_computer.session_closed.assert_not_called()
        ts.task_server.add_task_session.assert_called_with(msg.subtask_id, ts)
        ts.task_computer.task_given.assert_called_with(ctd)
        conn.close.assert_not_called()

        # Wrong key id -> failure
        __reset_mocks()
        header.task_owner.key = 'KEY_ID2'

        _prepare_and_react(ctd)
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        # Wrong task owner key id -> failure
        __reset_mocks()
        header.task_owner.key = 'KEY_ID2'

        _prepare_and_react(ctd)
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        # Wrong return port -> failure
        __reset_mocks()
        header.task_owner.key = 'KEY_ID'
        header.task_owner.pub_port = 0

        _prepare_and_react(ctd)
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        # Proper port and key -> proper execution
        __reset_mocks()
        header.task_owner.pub_port = 1112

        _prepare_and_react(ctd)
        conn.close.assert_not_called()

        # Allow custom code / no code in ComputeTaskDef -> failure
        __reset_mocks()
        env.allow_custom_main_program_file = True
        ctd['src_code'] = ""
        _prepare_and_react(ctd)
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        # Allow custom code / code in ComputerTaskDef -> proper execution
        __reset_mocks()
        ctd['src_code'] = "print 'Hello world!'"
        msg = _prepare_and_react(ctd)
        ts.task_computer.session_closed.assert_not_called()
        ts.task_server.add_task_session.assert_called_with(msg.subtask_id, ts)
        ts.task_computer.task_given.assert_called_with(ctd)
        conn.close.assert_not_called()

        # No environment available -> failure
        __reset_mocks()
        ts.task_server.get_environment_by_id.return_value = None
        _prepare_and_react(ctd)
        assert ts.err_msg == reasons.WrongEnvironment
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        # Envrionment is Docker environment but with different images -> failure
        __reset_mocks()
        ts.task_server.get_environment_by_id.return_value = \
            DockerEnvironmentMock(additional_images=[
                DockerImage("dockerix/xii", tag="323"),
                DockerImage("dockerix/xiii", tag="325"),
                DockerImage("dockerix/xiii")
            ])
        _prepare_and_react(ctd)
        assert ts.err_msg == reasons.WrongDockerImages
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        # Envrionment is Docker environment with proper images,
        # but no srouce code -> failure
        __reset_mocks()
        de = DockerEnvironmentMock(additional_images=[
            DockerImage("dockerix/xii", tag="323"),
            DockerImage("dockerix/xiii", tag="325"),
            DockerImage("dockerix/xiii", tag="323")
        ])
        ts.task_server.get_environment_by_id.return_value = de
        _prepare_and_react(ctd)
        assert ts.err_msg == reasons.NoSourceCode
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        # Proper Docker environment with source code
        __reset_mocks()
        file_name = os.path.join(self.path, "main_program_file")
        with open(file_name, 'w') as f:
            f.write("Hello world!")
        de.main_program_file = file_name
        msg = _prepare_and_react(ctd)
        ts.task_server.add_task_session.assert_called_with(msg.subtask_id, ts)
        ts.task_computer.task_given.assert_called_with(ctd)
        conn.close.assert_not_called()

    # pylint: enable=too-many-statements

    def test_get_resource(self):
        conn = BasicProtocol()
        conn.transport = Mock()
        conn.server = Mock()

        db = DataBuffer()

        sess = TaskSession(conn)
        sess.send = lambda m: db.append_bytes(
            m.serialize(),
        )
        sess._can_send = lambda *_: True
        sess.request_resource(str(uuid.uuid4()))

        self.assertTrue(
            message.base.Message.deserialize(db.buffered_data, lambda x: x)
        )

    def test_react_to_ack_reject_report_computed_task(self):
        task_keeper = CompTaskKeeper(pathlib.Path(self.path))

        session = self.task_session
        session.concent_service = MagicMock()
        session.task_manager.comp_task_keeper = task_keeper
        session.key_id = 'owner_id'

        cancel = session.concent_service.cancel_task_message

        ttc = msg_factories.tasks.TaskToComputeFactory()
        task_id = ttc.task_id
        subtask_id = ttc.subtask_id

        rct = msg_factories.tasks.ReportComputedTaskFactory(
            task_to_compute=ttc)

        msg_ack = message.tasks.AckReportComputedTask(
            report_computed_task=rct
        )
        msg_rej = message.tasks.RejectReportComputedTask(
            attached_task_to_compute=ttc
        )

        # Subtask is not known
        session._react_to_ack_report_computed_task(msg_ack)
        self.assertFalse(cancel.called)
        session._react_to_reject_report_computed_task(msg_rej)
        self.assertFalse(cancel.called)

        # Save subtask information
        task_owner = Node(key='owner_id')
        task = Mock(header=Mock(task_owner=task_owner))
        task_keeper.subtask_to_task[subtask_id] = task_id
        task_keeper.active_tasks[task_id] = task

        # Subtask is known
        with patch("golem.task.tasksession.get_task_message") as get_mock:
            get_mock.return_value = rct
            session._react_to_ack_report_computed_task(msg_ack)
            session.concent_service.submit_task_message.assert_called_once_with(
                subtask_id=msg_ack.subtask_id,
                msg=ANY,
                delay=ANY,
            )
        self.assertTrue(cancel.called)
        self.assert_concent_cancel(
            cancel.call_args[0], subtask_id, 'ForceReportComputedTask')

        cancel.reset_mock()
        session._react_to_reject_report_computed_task(msg_ack)
        self.assert_concent_cancel(
            cancel.call_args[0], subtask_id, 'ForceReportComputedTask')

    def test_react_to_resource_list(self):
        task_server = self.task_session.task_server

        client = 'test_client'
        version = 1.0
        peers = [{'TCP': ('127.0.0.1', 3282)}]
        msg = message.resources.ResourceList(resources=[['1'], ['2']],
                                             options=None)

        # Use locally saved hyperdrive client options
        self.task_session._react_to_resource_list(msg)
        call_options = task_server.pull_resources.call_args[1]

        assert task_server.get_download_options.called
        assert task_server.pull_resources.called
        assert isinstance(call_options['client_options'], Mock)

        # Use download options built by TaskServer
        client_options = ClientOptions(client, version,
                                       options={'peers': peers})
        task_server.get_download_options.return_value = client_options

        self.task_session.task_server.pull_resources.reset_mock()
        self.task_session._react_to_resource_list(msg)
        call_options = task_server.pull_resources.call_args[1]

        assert not isinstance(call_options['client_options'], Mock)
        assert call_options['client_options'].options['peers'] == peers

    def test_subtask_to_task(self):
        task_keeper = Mock(subtask_to_task=dict())
        mapping = dict()

        self.task_session.task_manager.comp_task_keeper = task_keeper
        self.task_session.task_manager.subtask2task_mapping = mapping
        task_keeper.subtask_to_task['sid_1'] = 'task_1'
        mapping['sid_2'] = 'task_2'

        assert self.task_session._subtask_to_task('sid_1', Actor.Provider)
        assert self.task_session._subtask_to_task('sid_2', Actor.Requestor)
        assert not self.task_session._subtask_to_task('sid_2', Actor.Provider)
        assert not self.task_session._subtask_to_task('sid_1', Actor.Requestor)

    def test_react_to_cannot_assign_task(self):
        self._test_react_to_cannot_assign_task()

    def test_react_to_cannot_assign_task_with_wrong_sender(self):
        self._test_react_to_cannot_assign_task("KEY_ID2", expected_requests=1)

    def _test_react_to_cannot_assign_task(self, key_id="KEY_ID",
                                          expected_requests=0):
        task_owner = Node(node_name="ABC", key="KEY_ID",
                          pub_addr="10.10.10.10", pub_port=2311)
        task_keeper = CompTaskKeeper(self.new_path)
        task_keeper.add_request(TaskHeader(environment='DEFAULT',
                                           task_id="abc",
                                           task_owner=task_owner), 20)
        assert task_keeper.active_tasks["abc"].requests == 1
        self.task_session.task_manager.comp_task_keeper = task_keeper
        msg_cat = message.tasks.CannotAssignTask(task_id="abc")
        self.task_session.key_id = key_id
        self.task_session._react_to_cannot_assign_task(msg_cat)
        assert task_keeper.active_tasks["abc"].requests == expected_requests

    def test_react_to_want_to_compute_no_handshake(self):
        mock_msg = Mock()
        mock_msg.concent_enabled = False

        self._prepare_handshake_test()

        ts = self.task_session

        ts._handshake_required = Mock()
        ts._handshake_required.return_value = True

        ts._start_handshake = Mock()

        with self.assertLogs(logger, level='WARNING'):
            ts._react_to_want_to_compute_task(mock_msg)

        ts._start_handshake.assert_called_with(ts.key_id)

    def test_react_to_want_to_compute_handshake_busy(self):
        mock_msg = Mock()
        mock_msg.concent_enabled = False

        self._prepare_handshake_test()

        ts = self.task_session

        ts._handshake_required = Mock()
        ts._handshake_required.return_value = False

        ts._handshake_in_progress = Mock()
        ts._handshake_in_progress.return_value = True

        with self.assertLogs(logger, level='WARNING'):
            ts._react_to_want_to_compute_task(mock_msg)

    def _prepare_handshake_test(self):
        ts = self.task_session.task_server
        tm = self.task_session.task_manager

        tm.is_my_task = Mock()
        tm.is_my_task.return_value = True

        tm.is_my_task = Mock()
        tm.is_my_task.return_value = True

        tm.should_wait_for_node = Mock()
        tm.should_wait_for_node.return_value = False

        ts.should_accept_provider = Mock()
        ts.should_accept_provider.return_value = True

        tm.check_next_subtask = Mock()
        tm.check_next_subtask.return_value = True


class ForceReportComputedTaskTestCase(testutils.DatabaseFixture,
                                      testutils.TempDirFixture):
    def setUp(self):
        testutils.DatabaseFixture.setUp(self)
        testutils.TempDirFixture.setUp(self)
        history.MessageHistoryService()
        self.ts = TaskSession(Mock())
        self.n = p2p_factories.Node()
        self.task_id = str(uuid.uuid4())
        self.subtask_id = str(uuid.uuid4())
        self.node_id = self.n.key

    def tearDown(self):
        testutils.DatabaseFixture.tearDown(self)
        testutils.TempDirFixture.tearDown(self)
        history.MessageHistoryService.instance = None

    @staticmethod
    def _mock_task_to_compute(task_id, subtask_id, node_id, **kwargs):
        task_to_compute = message.tasks.TaskToCompute(**kwargs)
        nmsg_dict = dict(
            task=task_id,
            subtask=subtask_id,
            node=node_id,
            msg_date=datetime.datetime.now(),
            msg_cls='TaskToCompute',
            msg_data=pickle.dumps(task_to_compute),
            local_role=model.Actor.Provider,
            remote_role=model.Actor.Requestor,
        )
        service = history.MessageHistoryService.instance
        service.add_sync(nmsg_dict)

    def assert_submit_task_message(self, subtask_id, wtr):
        self.ts.concent_service.submit_task_message.assert_called_once_with(
            subtask_id, ANY)

        msg = self.ts.concent_service.submit_task_message.call_args[0][1]
        self.assertEqual(msg.result_hash, 'sha1:' + wtr.package_sha1)

    def test_send_report_computed_task_concent_no_message(self):
        wtr = factories.taskserver.WaitingTaskResultFactory(owner=self.n)
        self.ts.send_report_computed_task(
            wtr, wtr.owner.pub_addr, wtr.owner.pub_port, self.n)
        self.ts.concent_service.submit.assert_not_called()

    def test_send_report_computed_task_concent_success(self):
        wtr = factories.taskserver.WaitingTaskResultFactory(
            xtask_id=self.task_id, xsubtask_id=self.subtask_id, owner=self.n)
        self._mock_task_to_compute(self.task_id, self.subtask_id, self.node_id,
                                   concent_enabled=True)
        self.ts.send_report_computed_task(
            wtr, wtr.owner.pub_addr, wtr.owner.pub_port, self.n)

        self.assert_submit_task_message(self.subtask_id, wtr)

    def test_send_report_computed_task_concent_success_many_files(self):
        result = []
        for i in range(100, 300, 99):
            p = pathlib.Path(self.tempdir) / str(i)
            with p.open('wb') as f:
                f.write(b'\0' * i * 2 ** 20)
            result.append(str(p))

        wtr = factories.taskserver.WaitingTaskResultFactory(
            xtask_id=self.task_id, xsubtask_id=self.subtask_id, owner=self.n,
            result=result, result_type=ResultType.FILES
        )
        self._mock_task_to_compute(self.task_id, self.subtask_id, self.node_id,
                                   concent_enabled=True)

        self.ts.send_report_computed_task(
            wtr, wtr.owner.pub_addr, wtr.owner.pub_port, self.n)

        self.assert_submit_task_message(self.subtask_id, wtr)

    def test_send_report_computed_task_concent_disabled(self):
        wtr = factories.taskserver.WaitingTaskResultFactory(
            task_id=self.task_id, subtask_id=self.subtask_id, owner=self.n)

        self._mock_task_to_compute(
            self.task_id, self.subtask_id, self.node_id, concent_enabled=False)

        self.ts.send_report_computed_task(
            wtr, wtr.owner.pub_addr, wtr.owner.pub_port, self.n)
        self.ts.concent_service.submit.assert_not_called()


class GetTaskMessageTest(TestCase):
    def test_get_task_message(self):
        msg = msg_factories.tasks.TaskToComputeFactory()
        with patch('golem.task.tasksession.history'
                   '.MessageHistoryService.get_sync_as_message',
                   Mock(return_value=msg)):
            msg_historical = get_task_message('TaskToCompute', 'foo', 'bar')
            self.assertEqual(msg, msg_historical)

    def test_get_task_message_fail(self):
        with patch('golem.task.tasksession.history'
                   '.MessageHistoryService.get_sync_as_message',
                   Mock(side_effect=history.MessageNotFound())):
            msg = get_task_message('TaskToCompute', 'foo', 'bar')
            self.assertIsNone(msg)


class SubtaskResultsAcceptedTest(TestCase):
    def setUp(self):
        self.task_session = TaskSession(Mock())
        self.task_server = Mock()
        self.task_session.task_server = self.task_server
        self.requestor_keys = cryptography.ECCx(None)
        self.requestor_key_id = encode_hex(self.requestor_keys.raw_pubkey)
        self.provider_keys = cryptography.ECCx(None)
        self.provider_key_id = encode_hex(self.provider_keys.raw_pubkey)

    def test_react_to_subtask_result_accepted(self):
        # given
        sra = msg_factories.tasks.SubtaskResultsAcceptedFactory(
            sign__privkey=self.requestor_keys.raw_privkey,
            task_to_compute__sign__privkey=self.requestor_keys.raw_privkey,
            task_to_compute__requestor_public_key=self.requestor_key_id,
            task_to_compute__want_to_compute_task__sign__privkey=(
                self.provider_keys.raw_privkey),
            task_to_compute__want_to_compute_task__provider_public_key=(
                self.provider_key_id),
        )
        self.task_server.keys_auth._private_key = \
            self.provider_keys.raw_privkey
        self.task_server.keys_auth.public_key = \
            self.provider_keys.raw_pubkey
        ctk = self.task_session.task_manager.comp_task_keeper
        ctk.get_node_for_task_id.return_value = self.requestor_key_id
        self.task_session.key_id = self.requestor_key_id
        self.task_server.client.transaction_system.is_income_expected\
                                                  .return_value = False

        # when
        self.task_session._react_to_subtask_result_accepted(sra)

        # then
        self.task_server.subtask_accepted.assert_called_once_with(
            self.requestor_key_id,
            sra.subtask_id,
            sra.task_to_compute.requestor_ethereum_address,  # noqa pylint:disable=no-member
            sra.task_to_compute.price,  # noqa pylint:disable=no-member
            sra.payment_ts,
        )
        cancel = self.task_session.concent_service.cancel_task_message
        cancel.assert_called_once_with(
            sra.subtask_id,
            'ForceSubtaskResults',
        )

    def test_react_with_wrong_key(self):
        # given
        key_id = "CDEF"
        sra = msg_factories.tasks.SubtaskResultsAcceptedFactory()
        ctk = self.task_session.task_manager.comp_task_keeper
        ctk.get_node_for_task_id.return_value = "ABC"
        self.task_session.key_id = key_id

        # when
        self.task_session._react_to_subtask_result_accepted(sra)

        # then
        self.task_server.subtask_accepted.assert_not_called()

    def test_react_with_unknown_key_and_expected_income(self):
        # given
        key_id = "CDEF"
        sra = msg_factories.tasks.SubtaskResultsAcceptedFactory()
        ctk = self.task_session.task_manager.comp_task_keeper
        ctk.get_node_for_task_id.return_value = None
        self.task_server.client.transaction_system.is_income_expected\
                                                  .return_value = True
        self.task_session.key_id = key_id

        # when
        self.task_session._react_to_subtask_result_accepted(sra)

        # then
        self.task_server.subtask_accepted.assert_called()

    def test_react_with_unknown_key_and_unexpected_income(self):
        # given
        key_id = "CDEF"
        sra = msg_factories.tasks.SubtaskResultsAcceptedFactory()
        ctk = self.task_session.task_manager.comp_task_keeper
        ctk.get_node_for_task_id.return_value = None
        self.task_server.client.transaction_system.is_income_expected\
                                                  .return_value = False
        self.task_session.key_id = key_id

        # when
        self.task_session._react_to_subtask_result_accepted(sra)

        # then
        self.task_server.subtask_accepted.assert_not_called()

    def test_result_received(self):
        self.task_server.keys_auth._private_key = \
            self.requestor_keys.raw_privkey
        self.task_server.keys_auth.public_key = \
            self.requestor_keys.raw_pubkey

        def computed_task_received(*args):
            args[3]()

        self.task_session.task_manager = Mock()
        self.task_session.task_manager.computed_task_received = \
            computed_task_received

        rct = msg_factories.tasks.ReportComputedTaskFactory()
        ttc = rct.task_to_compute
        extra_data = dict(
            result=pickle.dumps({'stdout': 'xyz'}),
            result_type=ResultType.DATA,
            subtask_id=ttc.compute_task_def.get('subtask_id')  # noqa pylint:disable=no-member
        )

        self.task_session.send = Mock()

        history_dict = {
            'TaskToCompute': ttc,
            'ReportComputedTask': rct,
        }
        with patch('golem.task.tasksession.get_task_message',
                   side_effect=lambda mcn, *_: history_dict[mcn]):
            self.task_session.result_received(extra_data)

        assert self.task_session.send.called
        sra = self.task_session.send.call_args[0][0] # noqa pylint:disable=unsubscriptable-object
        self.assertIsInstance(sra.task_to_compute, message.tasks.TaskToCompute)
        self.assertTrue(sra.task_to_compute.sig)
        self.assertTrue(
            sra.task_to_compute.verify_signature(
                self.requestor_keys.raw_pubkey
            )
        )


class ReportComputedTaskTest(ConcentMessageMixin, LogTestCase):

    @staticmethod
    def _create_pull_package(result):
        def pull_package(*_, **kwargs):
            success = kwargs.get('success')
            error = kwargs.get('error')
            if result:
                success(Mock())
            else:
                error(Exception('Pull failed'))

        return pull_package

    def setUp(self):
        self.ecc = cryptography.ECCx(None)
        self.node_id = encode_hex(self.ecc.raw_pubkey)
        self.task_id = idgenerator.generate_id_from_hex(self.node_id)
        self.subtask_id = idgenerator.generate_id_from_hex(self.node_id)

        ts = TaskSession(Mock())
        ts.result_received = Mock()
        ts.key_id = "ABC"
        ts.task_manager.get_node_id_for_subtask.return_value = ts.key_id
        ts.task_manager.subtask2task_mapping = {
            self.subtask_id: self.task_id,
        }
        ts.task_manager.tasks = {
            self.task_id: Mock()
        }
        ts.task_manager.tasks_states = {
            self.task_id: Mock(subtask_states={
                self.subtask_id: Mock(deadline=calendar.timegm(time.gmtime()))
            })
        }
        ts.task_server.task_keeper.task_headers = {}
        ecc = Mock()
        ecc.get_privkey.return_value = os.urandom(32)
        ts.task_server.keys_auth.ecc = ecc
        self.ts = ts

        gsam = patch('golem.network.concent.helpers.history'
                     '.MessageHistoryService.get_sync_as_message',
                     Mock(side_effect=history.MessageNotFound))
        gsam.start()
        self.addCleanup(gsam.stop)

    def _prepare_report_computed_task(self, **kwargs):
        return msg_factories.tasks.ReportComputedTaskFactory(
            task_to_compute__task_id=self.task_id,
            task_to_compute__subtask_id=self.subtask_id,
            **kwargs,
        )

    def test_result_received(self):
        msg = self._prepare_report_computed_task()
        self.ts.task_manager.task_result_manager.pull_package = \
            self._create_pull_package(True)

        with patch('golem.network.concent.helpers.process_report_computed_task',
                   return_value=message.tasks.AckReportComputedTask()):
            self.ts._react_to_report_computed_task(msg)
        self.assertTrue(self.ts.task_server.verify_results.called)

        cancel = self.ts.concent_service.cancel_task_message
        self.assert_concent_cancel(
            cancel.call_args[0], self.subtask_id, 'ForceGetTaskResult')

    def test_reject_result_pull_failed_no_concent(self):
        msg = self._prepare_report_computed_task(
            task_to_compute__concent_enabled=False)

        with patch('golem.network.concent.helpers.history.add'):
            self.ts.task_manager.task_result_manager.pull_package = \
                self._create_pull_package(False)

        with patch('golem.task.tasksession.get_task_message', return_value=msg):
            with patch('golem.network.concent.helpers.'
                       'process_report_computed_task',
                       return_value=message.tasks.AckReportComputedTask()):
                self.ts._react_to_report_computed_task(msg)
        assert self.ts.task_server.reject_result.called
        assert self.ts.task_manager.task_computation_failure.called

    def test_reject_result_pull_failed_with_concent(self):
        msg = self._prepare_report_computed_task(
            task_to_compute__concent_enabled=True)

        self.ts.task_manager.task_result_manager.pull_package = \
            self._create_pull_package(False)

        with patch('golem.network.concent.helpers.process_report_computed_task',
                   return_value=message.tasks.AckReportComputedTask()):
            self.ts._react_to_report_computed_task(msg)
        stm = self.ts.concent_service.submit_task_message
        self.assertEqual(stm.call_count, 2)

        self.assert_concent_submit(stm.call_args_list[0][0], self.subtask_id,
                                   message.concents.ForceGetTaskResult)
        self.assert_concent_submit(stm.call_args_list[1][0], self.subtask_id,
                                   message.concents.ForceGetTaskResult)

        # ensure the first call is delayed
        self.assertGreater(stm.call_args_list[0][0][2], datetime.timedelta(0))
        # ensure the second one is not
        self.assertEqual(len(stm.call_args_list[1][0]), 2)
