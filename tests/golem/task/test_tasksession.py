# pylint: disable=too-many-lines, protected-access
import calendar
import datetime
import os
import pathlib
import pickle
import random
import time
import typing
import uuid
from unittest import TestCase
from unittest.mock import patch, ANY, Mock, MagicMock

import faker
from golem_messages import factories as msg_factories
from golem_messages import idgenerator
from golem_messages import message
from golem_messages import cryptography
from golem_messages.factories.datastructures import p2p as dt_p2p_factory
from golem_messages.factories.datastructures import tasks as dt_tasks_factory
from golem_messages.utils import encode_hex
from pydispatch import dispatcher

import twisted.internet.address
from twisted.internet.defer import Deferred

import golem
from golem import model, testutils
from golem.config.active import EthereumConfig
from golem.core import variables
from golem.core.keysauth import KeysAuth
from golem.docker.environment import DockerEnvironment
from golem.docker.image import DockerImage
from golem.network.hyperdrive import client as hyperdrive_client
from golem.network import history
from golem.network.hyperdrive.client import HyperdriveClientOptions
from golem.task import taskstate
from golem.task.taskkeeper import CompTaskKeeper
from golem.task.tasksession import TaskSession, logger, get_task_message
from golem.tools.assertlogs import LogTestCase

fake = faker.Faker()


def fill_slots(msg):
    for slot in msg.__slots__:
        if hasattr(msg, slot):
            continue
        setattr(msg, slot, None)


class DockerEnvironmentMock(DockerEnvironment):
    DOCKER_IMAGE = ""
    DOCKER_TAG = ""
    ENV_ID = ""
    SHORT_DESCRIPTION = ""


class TestTaskSessionPep8(testutils.PEP8MixIn, TestCase):
    PEP8_FILES = [
        'golem/task/tasksession.py',
        'tests/golem/task/test_tasksession.py',
    ]


class ConcentMessageMixin():
    def assert_concent_cancel(self, mock_call, subtask_id, message_class_name):
        self.assertEqual(mock_call[0], subtask_id)
        self.assertEqual(mock_call[1], message_class_name)

    def assert_concent_submit(self, mock_call, subtask_id, message_class):
        self.assertEqual(mock_call[0], subtask_id)
        self.assertIsInstance(mock_call[1], message_class)


def _offerpool_add(*_):
    res = Deferred()
    res.callback(True)
    return res


# pylint:disable=no-member,too-many-instance-attributes
@patch('golem.task.tasksession.OfferPool.add', _offerpool_add)
@patch('golem.task.tasksession.get_provider_efficiency', Mock())
@patch('golem.task.tasksession.get_provider_efficacy', Mock())
class TaskSessionTaskToComputeTest(TestCase):
    def setUp(self):
        self.maxDiff = None
        self.requestor_keys = cryptography.ECCx(None)
        self.requestor_key = encode_hex(self.requestor_keys.raw_pubkey)
        self.provider_keys = cryptography.ECCx(None)
        self.provider_key = encode_hex(self.provider_keys.raw_pubkey)

        self.task_manager = Mock(tasks_states={}, tasks={})
        self.task_manager.task_finished.return_value = False
        server = Mock(task_manager=self.task_manager)
        server.get_key_id = lambda: self.provider_key
        server.get_share_options.return_value = None
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
        ts.task_server.keys_auth.public_key = self.requestor_keys.raw_pubkey
        ts.conn.send_message.side_effect = lambda msg: msg._fake_sign()
        return ts

    def _get_task_parameters(self):
        return {
            'node_name': self.node_name,
            'perf_index': 1030,
            'price': 30,
            'max_resource_size': 3,
            'max_memory_size': 1,
            'task_header': self._get_task_header()
        }

    def _get_wtct(self):
        msg = msg_factories.tasks.WantToComputeTaskFactory(
            concent_enabled=self.use_concent,
            **self._get_task_parameters(),
        )
        msg.sign_message(self.provider_keys.raw_privkey)  # noqa pylint: disable=no-member, no-value-for-parameter
        return msg

    def _fake_add_task(self):
        task_header = self._get_task_header()
        self.task_manager.tasks[self.task_id] = Mock(header=task_header)

    def _get_task_header(self):
        task_header = dt_tasks_factory.TaskHeaderFactory(
            task_id=self.task_id,
            task_owner=dt_p2p_factory.Node(
                key=self.requestor_key,
            ),
            subtask_timeout=1,
            max_price=1, )
        task_header.sign(self.requestor_keys.raw_privkey)  # noqa pylint: disable=no-value-for-parameter
        return task_header

    def _set_task_state(self):
        task_state = taskstate.TaskState()
        task_state.package_hash = '667'
        task_state.package_size = 42
        self.conn.server.task_manager.tasks_states[self.task_id] = task_state
        return task_state

    @patch('golem.network.history.MessageHistoryService.instance')
    def test_cannot_assign_task_provider_not_accepted(self, *_):
        mt = self._get_wtct()
        ts2 = self._get_requestor_tasksession(accept_provider=False)
        self._fake_add_task()

        ctd = message.tasks.ComputeTaskDef(task_id=mt.task_id)
        self._set_task_state()

        ts2.task_manager.get_next_subtask.return_value = ctd
        ts2.task_manager.should_wait_for_node.return_value = False
        ts2.task_server.should_accept_provider.return_value = False
        ts2.interpret(mt)
        ms = ts2.conn.send_message.call_args[0][0]
        self.assertIsInstance(ms, message.tasks.CannotAssignTask)
        self.assertEqual(ms.task_id, mt.task_id)

    def test_cannot_assign_task_finished(self, *_):
        wtct: message.tasks.WantToComputeTask = self._get_wtct()
        session = self._get_requestor_tasksession()
        self._fake_add_task()
        self._set_task_state()
        self.task_manager.task_finished.return_value = True
        session.interpret(wtct)
        session.conn.send_message.assert_called_once()
        response = session.conn.send_message.call_args[0][0]
        self.assertIsInstance(response, message.tasks.CannotAssignTask)
        self.assertIs(
            response.reason,
            message.tasks.CannotAssignTask.REASON.TaskFinished,
        )

    @patch('golem.network.history.MessageHistoryService.instance')
    def test_cannot_assign_task_wrong_ctd(self, *_):
        mt = self._get_wtct()
        ts2 = self._get_requestor_tasksession()
        self._fake_add_task()

        self._set_task_state()

        ts2.task_manager.should_wait_for_node.return_value = False
        ts2.task_manager.check_next_subtask.return_value = False
        ts2.interpret(mt)
        ts2.task_manager.check_next_subtask.assert_called_once_with(
            mt.task_id,
            mt.price,
        )
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
        assert ts2.task_manager.task_computation_cancelled.called

    def test_cannot_compute_task_bad_subtask_id(self):
        ts2 = self._get_requestor_tasksession()
        ts2.task_manager.task_computation_failure.called = False
        ts2.task_manager.get_node_id_for_subtask.return_value = "___"
        ts2._react_to_cannot_compute_task(message.tasks.CannotComputeTask(
            reason=message.tasks.CannotComputeTask.REASON.WrongCTD,
            task_to_compute=None,
        ))
        assert not ts2.task_manager.task_computation_failure.called

    def _fake_send_ttc(self):
        wtct = self._get_wtct()
        ts = self._get_requestor_tasksession(accept_provider=True)
        self._fake_add_task()

        ctd = msg_factories.tasks.ComputeTaskDefFactory(task_id=wtct.task_id)
        task_state = self._set_task_state()

        ts.task_manager.get_next_subtask.return_value = ctd
        ts.task_manager.should_wait_for_node.return_value = False
        ts.conn.send_message.side_effect = \
            lambda msg: msg.sign_message(self.requestor_keys.raw_privkey)
        options = HyperdriveClientOptions("CLI1", 0.3)
        ts.task_server.get_share_options.return_value = options
        ts.interpret(wtct)
        ts.conn.send_message.assert_called_once()
        ttc = ts.conn.send_message.call_args[0][0]
        self.assertIsInstance(ttc, message.tasks.TaskToCompute)
        return ttc, wtct, ctd, task_state, ts

    @patch('golem.network.history.MessageHistoryService.instance')
    def test_request_task(self, *_):
        ttc, wtct, ctd, task_state, ts = self._fake_send_ttc()
        expected = [
            ['requestor_id', self.requestor_key],
            ['provider_id', ts.key_id],
            ['requestor_public_key', self.requestor_key],
            ['requestor_ethereum_public_key', self.requestor_key],
            ['compute_task_def', ctd],
            ['want_to_compute_task',
             (False, (wtct.header, wtct.sig, wtct.slots()))],
            ['package_hash', 'sha1:' + task_state.package_hash],
            ['concent_enabled', self.use_concent],
            ['price', 1],
            ['size', task_state.package_size],
            ['ethsig', ttc.ethsig],
            ['resources_options', {'client_id': 'CLI1', 'version': 0.3,
                                   'options': {}}],
            ['promissory_note_sig',
             ttc._get_promissory_note().sign(self.requestor_keys.raw_privkey)],
            ['concent_promissory_note_sig',
             ttc._get_concent_promissory_note(
                 getattr(EthereumConfig, 'deposit_contract_address')
             ).sign(
                 self.requestor_keys.raw_privkey)],
        ]
        self.assertCountEqual(ttc.slots(), expected)

    def test_task_to_compute_eth_signature(self):
        ttc, _, __, ___, ____ = self._fake_send_ttc()
        self.assertEqual(ttc.requestor_ethereum_public_key, self.requestor_key)
        self.assertTrue(ttc.verify_ethsig())

    def test_task_to_compute_promissory_notes(self):
        ttc, _, __, ___, ____ = self._fake_send_ttc()
        self.assertTrue(ttc.verify_promissory_note())
        self.assertTrue(ttc.verify_concent_promissory_note(
            getattr(EthereumConfig, 'deposit_contract_address')
        ))


# pylint:enable=no-member

@patch("golem.network.nodeskeeper.store")
class TaskSessionTestBase(ConcentMessageMixin, LogTestCase,
                          testutils.TempDirFixture):

    def setUp(self):
        super().setUp()
        random.seed()
        self.conn = Mock()
        self.task_session = TaskSession(self.conn)
        self.task_session.key_id = 'deadbeef'
        self.task_session.task_server.get_share_options.return_value = \
            hyperdrive_client.HyperdriveClientOptions('1', 1.0)
        self.keys = KeysAuth(
            datadir=self.path,
            difficulty=4,
            private_key_name='prv',
            password='',
        )
        self.task_session.task_server.keys_auth = self.keys
        self.task_session.task_server.sessions = {}
        self.task_session.task_manager.task_finished.return_value = False
        self.pubkey = self.keys.public_key
        self.privkey = self.keys._private_key


class TaskSessionReactToTaskToComputeTest(TaskSessionTestBase):

    def setUp(self):
        super().setUp()
        self.task_session.task_computer.has_assigned_task.return_value = False
        self.task_session.concent_service.enabled = False
        self.task_session.send = Mock(
            side_effect=lambda msg: print(f"send {msg}"))

        self.env = Mock()
        self.env.docker_images = [DockerImage("dockerix/xii", tag="323")]
        self.task_session.task_server.get_environment_by_id.return_value = \
            self.env

        self.header = self.task_session.task_manager.\
            comp_task_keeper.get_task_header()
        self.header.task_owner.key = self.task_session.key_id
        self.header.task_owner.pub_addr = '10.10.10.10'
        self.header.task_owner.pub_port = 1112

        self.reasons = message.tasks.CannotComputeTask.REASON

    @staticmethod
    def ctd(**kwargs):
        return msg_factories.tasks.ComputeTaskDefFactory(
            docker_images=[
                DockerImage("dockerix/xiii", tag="323").to_dict(),
            ],
            **kwargs
        )

    def ttc_prepare_and_react(
            self,
            ctd: typing.Optional[
                typing.Union[
                    message.tasks.ComputeTaskDef, bool
                ]
            ] = False,  # noqa pylint: disable=bad-whitespace
            resource_size=102400,
            **kwargs,
    ):
        if ctd is False:
            ctd = self.ctd()

        ttc = msg_factories.tasks.TaskToComputeFactory(
            compute_task_def=ctd,
            **kwargs,
        )
        ttc.want_to_compute_task.provider_public_key = encode_hex(
            self.keys.ecc.raw_pubkey)
        ttc.want_to_compute_task.sign_message(self.keys.ecc.raw_privkey)  # noqa pylint: disable=no-member
        ttc._fake_sign()
        self.task_session.task_server.task_keeper.task_headers = {
            ttc.task_id: MagicMock(),
        }
        self.task_session.task_server.task_keeper\
            .task_headers[ttc.task_id].subtasks_count = 10
        self.task_session.task_server.client.transaction_system.\
            get_available_gnt.return_value = ttc.price * 10
        self.task_session.task_server.\
            config_desc.max_resource_size = resource_size
        self.task_session._react_to_task_to_compute(ttc)
        return ttc

    def assertCannotComputeTask(self, reason):
        self.task_session.task_manager.comp_task_keeper\
            .receive_subtask.assert_not_called()
        assert self.conn.close.called
        self.task_session.send.assert_called_once_with(ANY)
        msg = self.task_session.send.call_args[0][0]
        self.assertIsInstance(msg, message.tasks.CannotComputeTask)
        self.assertIs(msg.reason, reason)

    def test_react_to_task_to_compute(self):
        ctd = self.ctd()
        ttc = self.ttc_prepare_and_react(ctd)
        self.task_session.task_manager.\
            comp_task_keeper.receive_subtask.assert_called_with(ttc)
        self.task_session.task_server.task_given.assert_called_with(
            self.header.task_owner.key,
            ctd,
            ttc.price,
        )
        self.conn.close.assert_not_called()

    def test_no_ctd(self, *_):
        # ComputeTaskDef is None -> failure
        self.ttc_prepare_and_react(None)
        self.task_session.task_server.task_given.assert_not_called()
        self.task_session.task_manager.\
            comp_task_keeper.receive_subtask.assert_not_called()
        self.task_session.send.assert_not_called()
        assert self.conn.close.called

    def test_wrong_key_id(self):
        # Wrong task owner key id -> failure
        self.header.task_owner.key = 'KEY_ID2'
        self.ttc_prepare_and_react()
        self.assertCannotComputeTask(self.reasons.WrongKey)

    def test_fail_wrong_port(self):
        # Wrong return port -> failure
        self.header.task_owner.pub_port = 0
        self.ttc_prepare_and_react()
        self.assertCannotComputeTask(self.reasons.WrongAddress)

    def test_correct_port_and_key(self):
        # Proper port and key -> proper execution
        self.header.task_owner.pub_port = 1112
        self.ttc_prepare_and_react()
        self.conn.close.assert_not_called()

    def test_fail_wrong_data_size(self):
        # Wrong data size -> failure
        self.ttc_prepare_and_react(resource_size=1024)
        self.assertCannotComputeTask(self.reasons.ResourcesTooBig)

    def test_ctd_custom_code(self):
        # Allow custom code / code in ComputerTaskDef -> proper execution
        ctd = self.ctd(extra_data__src_code="print 'Hello world!'")
        ttc = self.ttc_prepare_and_react(ctd)
        self.task_session.task_server.task_given.assert_called_with(
            self.header.task_owner.key,
            ctd,
            ttc.price,
        )
        self.conn.close.assert_not_called()

    def test_fail_no_environment_available(self):
        # No environment available -> failure
        self.task_session.task_server.get_environment_by_id.return_value = None
        self.ttc_prepare_and_react()
        self.assertCannotComputeTask(self.reasons.WrongEnvironment)

    def test_fail_different_docker_images(self):
        # Environment is a Docker environment but with different images
        self.task_session.task_server.get_environment_by_id.return_value = \
            DockerEnvironmentMock(additional_images=[
                DockerImage("dockerix/xii", tag="323"),
                DockerImage("dockerix/xiii", tag="325"),
                DockerImage("dockerix/xiii")
            ])
        self.ttc_prepare_and_react()
        self.assertCannotComputeTask(self.reasons.WrongDockerImages)


class TestTaskSession(TaskSessionTestBase):
    @patch('golem.task.tasksession.TaskSession.send')
    def test_hello(self, send_mock, *_):
        self.task_session.conn.server.get_key_id.return_value = key_id = \
            'key id%d' % (random.random() * 1000,)
        node = dt_p2p_factory.Node()
        self.task_session.task_server.client.node = node
        self.task_session.send_hello()
        expected = [
            ['rand_val', self.task_session.rand_val],
            ['proto_id', variables.PROTOCOL_CONST.ID],
            ['node_name', None],
            ['node_info', node.to_dict()],
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

    def _get_srr(self, key2=None, concent=False):
        key1 = 'known'
        key2 = key2 or key1
        srr = msg_factories.tasks.SubtaskResultsRejectedFactory(**{
            'report_computed_task__task_to_compute__concent_enabled': concent,
            'report_computed_task__'
            'task_to_compute__'
            'want_to_compute_task__'
            'provider_public_key': encode_hex(self.pubkey)
        })
        srr._fake_sign()
        ctk = self.task_session.task_manager.comp_task_keeper
        ctk.get_node_for_task_id.return_value = key1
        self.task_session.key_id = key2
        return srr

    def __call_react_to_srr(self, srr):
        with patch('golem.task.tasksession.TaskSession.dropped') as dropped:
            self.task_session._react_to_subtask_results_rejected(srr)
        dropped.assert_called_once_with()

    def test_result_rejected(self, *_):
        dispatch_listener = Mock()
        dispatcher.connect(dispatch_listener, signal='golem.message')

        srr = self._get_srr()
        self.__call_react_to_srr(srr)

        self.task_session.task_server.subtask_rejected.assert_called_once_with(
            sender_node_id=self.task_session.key_id,
            subtask_id=srr.report_computed_task.subtask_id,  # noqa pylint:disable=no-member
        )

        dispatch_listener.assert_called_once_with(
            event='received',
            signal='golem.message',
            message=srr,
            sender=ANY,
        )

    def test_result_rejected_with_wrong_key(self, *_):
        srr = self._get_srr(key2='notmine')
        self.__call_react_to_srr(srr)
        self.task_session.task_server.subtask_rejected.assert_not_called()

    def test_result_rejected_with_concent(self, *_):
        srr = self._get_srr(concent=True)

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
        srv = kwargs['msg']
        self.assertIsInstance(srv, message.concents.SubtaskResultsVerify)
        self.assertEqual(srv.subtask_results_rejected, srr)
        self.assertTrue(srv.verify_concent_promissory_note(
            getattr(EthereumConfig, 'deposit_contract_address')
        ))

    @patch('golem.task.taskkeeper.ProviderStatsManager', Mock())
    def test_react_to_ack_reject_report_computed_task(self, *_):
        task_keeper = CompTaskKeeper(pathlib.Path(self.path))

        session = self.task_session
        session.conn.server.client.concent_service = MagicMock()
        session.task_manager.comp_task_keeper = task_keeper
        session.key_id = 'owner_id'

        cancel = session.concent_service.cancel_task_message

        ttc = msg_factories.tasks.TaskToComputeFactory(
            concent_enabled=True,
        )
        task_id = ttc.task_id
        subtask_id = ttc.subtask_id

        rct = msg_factories.tasks.ReportComputedTaskFactory(
            task_to_compute=ttc)

        msg_ack = message.tasks.AckReportComputedTask(
            report_computed_task=rct
        )
        msg_ack._fake_sign()
        msg_rej = message.tasks.RejectReportComputedTask(
            attached_task_to_compute=ttc
        )
        msg_rej._fake_sign()

        # Subtask is not known
        session._react_to_ack_report_computed_task(msg_ack)
        self.assertFalse(cancel.called)
        session._react_to_reject_report_computed_task(msg_rej)
        self.assertFalse(cancel.called)

        # Save subtask information
        task_owner = dt_p2p_factory.Node(key='owner_id')
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

    @patch('golem.task.taskkeeper.ProviderStatsManager', Mock())
    def test_react_to_cannot_assign_task(self, *_):
        self._test_react_to_cannot_assign_task()

    @patch('golem.task.taskkeeper.ProviderStatsManager', Mock())
    def test_react_to_cannot_assign_task_with_wrong_sender(self, *_):
        self._test_react_to_cannot_assign_task("KEY_ID2", expected_requests=1)

    def _test_react_to_cannot_assign_task(
            self,
            key_id="KEY_ID",
            expected_requests=0,
    ):
        task_keeper = CompTaskKeeper(self.new_path)
        task_keeper.add_request(
            dt_tasks_factory.TaskHeaderFactory(
                task_id="abc",
                task_owner=dt_p2p_factory.Node(
                    key="KEY_ID",
                ),
                subtask_timeout=1,
                max_price=1,
            ),
            20,
        )
        assert task_keeper.active_tasks["abc"].requests == 1
        self.task_session.task_manager.comp_task_keeper = task_keeper
        msg_cat = message.tasks.CannotAssignTask(task_id="abc")
        msg_cat._fake_sign()
        self.task_session.key_id = key_id
        self.task_session._react_to_cannot_assign_task(msg_cat)
        self.assertEqual(
            task_keeper.active_tasks["abc"].requests,
            expected_requests,
        )

    def test_react_to_want_to_compute_no_handshake(self, *_):
        mock_msg = Mock()
        mock_msg.concent_enabled = False

        self._prepare_handshake_test()

        ts = self.task_session

        ts._handshake_required = Mock()
        ts._handshake_required.return_value = True

        with self.assertLogs(logger, level='WARNING'):
            ts._react_to_want_to_compute_task(mock_msg)

        ts.task_server.start_handshake.assert_called_once_with(ts.key_id)

    def test_react_to_want_to_compute_handshake_busy(self, *_):
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

    def test_react_to_want_to_compute_invalid_task_header_signature(self, *_):
        different_requestor_keys = cryptography.ECCx(None)
        provider_keys = cryptography.ECCx(None)
        wtct = msg_factories.tasks.WantToComputeTaskFactory(
            sign__privkey=provider_keys.raw_privkey,
            task_header__sign__privkey=different_requestor_keys.raw_privkey,
        )
        self._prepare_handshake_test()
        ts = self.task_session
        ts.verified = True

        ts._react_to_want_to_compute_task(wtct)

        sent_msg = ts.conn.send_message.call_args[0][0]
        self.assertIsInstance(sent_msg, message.tasks.CannotAssignTask)
        self.assertEqual(sent_msg.reason,
                         message.tasks.CannotAssignTask.REASON.NotMyTask)

    def test_react_to_want_to_compute_not_my_task_id(self, *_):
        provider_keys = cryptography.ECCx(None)
        wtct = msg_factories.tasks.WantToComputeTaskFactory(
            sign__privkey=provider_keys.raw_privkey,
            task_header__sign__privkey=self.privkey,
        )
        self._prepare_handshake_test()
        ts = self.task_session
        ts.verified = True
        ts.task_manager.is_my_task.return_value = False

        ts._react_to_want_to_compute_task(wtct)

        sent_msg = ts.conn.send_message.call_args[0][0]
        self.assertIsInstance(sent_msg, message.tasks.CannotAssignTask)
        self.assertEqual(sent_msg.reason,
                         message.tasks.CannotAssignTask.REASON.NotMyTask)

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


class WaitingForResultsTestCase(
        testutils.DatabaseFixture,
        testutils.TempDirFixture,
):
    def setUp(self):
        testutils.DatabaseFixture.setUp(self)
        testutils.TempDirFixture.setUp(self)
        history.MessageHistoryService()
        self.ts = TaskSession(Mock())
        self.ts.conn.send_message.side_effect = \
            lambda msg: msg._fake_sign()
        self.ts.task_server.get_node_name.return_value = "Zażółć gęślą jaźń"
        requestor_keys = KeysAuth(
            datadir=self.path,
            difficulty=4,
            private_key_name='prv',
            password='',
        )
        self.ts.task_server.get_key_id.return_value = "key_id"
        self.ts.key_id = requestor_keys.key_id
        self.ts.task_server.get_share_options.return_value = \
            hyperdrive_client.HyperdriveClientOptions('1', 1.0)

        keys_auth = KeysAuth(
            datadir=self.path,
            difficulty=4,
            private_key_name='prv',
            password='',
        )
        self.ts.task_server.keys_auth = keys_auth
        self.ts.concent_service.variant = variables.CONCENT_CHOICES['test']
        ttc_prefix = 'task_to_compute'
        hdr_prefix = f'{ttc_prefix}__want_to_compute_task__task_header'
        self.msg = msg_factories.tasks.WaitingForResultsFactory(
            sign__privkey=requestor_keys.ecc.raw_privkey,
            **{
                f'{ttc_prefix}__sign__privkey': requestor_keys.ecc.raw_privkey,
                f'{ttc_prefix}__requestor_public_key':
                    encode_hex(requestor_keys.ecc.raw_pubkey),
                f'{ttc_prefix}__want_to_compute_task__sign__privkey':
                    keys_auth.ecc.raw_privkey,
                f'{ttc_prefix}__want_to_compute_task__provider_public_key':
                    encode_hex(keys_auth.ecc.raw_pubkey),
                f'{hdr_prefix}__sign__privkey':
                    requestor_keys.ecc.raw_privkey,
                f'{hdr_prefix}__requestor_public_key':
                    encode_hex(requestor_keys.ecc.raw_pubkey),
            },
        )

    def test_task_server_notification(self, *_):
        self.ts._react_to_waiting_for_results(self.msg)
        self.ts.task_server.subtask_waiting.assert_called_once_with(
            task_id=self.msg.task_id,
            subtask_id=self.msg.subtask_id,
        )


class ForceReportComputedTaskTestCase(testutils.DatabaseFixture,
                                      testutils.TempDirFixture):
    def setUp(self):
        testutils.DatabaseFixture.setUp(self)
        testutils.TempDirFixture.setUp(self)
        history.MessageHistoryService()
        self.ts = TaskSession(Mock())
        self.ts.conn.send_message.side_effect = \
            lambda msg: msg._fake_sign()
        self.ts.task_server.get_node_name.return_value = "Zażółć gęślą jaźń"
        self.ts.task_server.get_key_id.return_value = "key_id"
        self.ts.key_id = 'unittest_key_id'
        self.ts.task_server.get_share_options.return_value = \
            hyperdrive_client.HyperdriveClientOptions('1', 1.0)

        keys_auth = KeysAuth(
            datadir=self.path,
            difficulty=4,
            private_key_name='prv',
            password='',
        )
        self.ts.task_server.keys_auth = keys_auth
        self.n = dt_p2p_factory.Node()
        self.task_id = str(uuid.uuid4())
        self.subtask_id = str(uuid.uuid4())
        self.node_id = self.n.key

    def tearDown(self):
        testutils.DatabaseFixture.tearDown(self)
        testutils.TempDirFixture.tearDown(self)
        history.MessageHistoryService.instance = None

    @staticmethod
    def _mock_task_to_compute(task_id, subtask_id, node_id, **kwargs):
        task_to_compute = msg_factories.tasks.TaskToComputeFactory(**kwargs)
        task_to_compute._fake_sign()
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


class GetTaskMessageTest(TestCase):
    def test_get_task_message(self):
        msg = msg_factories.tasks.TaskToComputeFactory()
        with patch('golem.task.tasksession.history'
                   '.MessageHistoryService.get_sync_as_message',
                   Mock(return_value=msg)):
            msg_historical = get_task_message('TaskToCompute', 'foo', 'bar',
                                              'baz')
            self.assertEqual(msg, msg_historical)

    def test_get_task_message_fail(self):
        with patch('golem.task.tasksession.history'
                   '.MessageHistoryService.get_sync_as_message',
                   Mock(side_effect=history.MessageNotFound())):
            msg = get_task_message('TaskToCompute', 'foo', 'bar', 'baz')
            self.assertIsNone(msg)


class SubtaskResultsAcceptedTest(TestCase):
    def setUp(self):
        self.task_session = TaskSession(Mock())
        self.task_session.verified = True
        self.task_server = Mock()
        self.task_session.conn.server = self.task_server
        self.requestor_keys = cryptography.ECCx(None)
        self.requestor_key_id = encode_hex(self.requestor_keys.raw_pubkey)
        self.provider_keys = cryptography.ECCx(None)
        self.provider_key_id = encode_hex(self.provider_keys.raw_pubkey)

    def test_react_to_subtask_results_accepted(self):
        # given
        rct = msg_factories.tasks.ReportComputedTaskFactory(
            task_to_compute__sign__privkey=self.requestor_keys.raw_privkey,
            task_to_compute__requestor_public_key=self.requestor_key_id,
            task_to_compute__want_to_compute_task__sign__privkey=(
                self.provider_keys.raw_privkey),
            task_to_compute__want_to_compute_task__provider_public_key=(
                self.provider_key_id),
        )
        sra = msg_factories.tasks.SubtaskResultsAcceptedFactory(
            sign__privkey=self.requestor_keys.raw_privkey,
            report_computed_task=rct,
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

        dispatch_listener = Mock()
        dispatcher.connect(dispatch_listener, signal='golem.message')

        # when
        self.task_session._react_to_subtask_results_accepted(sra)

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

        dispatch_listener.assert_called_once_with(
            event='received',
            signal='golem.message',
            message=sra,
            sender=ANY,
        )

    def test_react_with_wrong_key(self):
        # given
        key_id = "CDEF"
        sra = msg_factories.tasks.SubtaskResultsAcceptedFactory()
        sra._fake_sign()
        ctk = self.task_session.task_manager.comp_task_keeper
        ctk.get_node_for_task_id.return_value = "ABC"
        self.task_session.key_id = key_id

        # when
        self.task_session._react_to_subtask_results_accepted(sra)

        # then
        self.task_server.subtask_accepted.assert_not_called()


@patch("golem.task.tasksession.TaskSession.verify_owners", return_value=True)
@patch("golem.network.transport.msg_queue.put")
class ReportComputedTaskTest(
        ConcentMessageMixin,
        LogTestCase,
        testutils.TempDirFixture,
):

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
        super().setUp()
        keys_auth = KeysAuth(
            datadir=self.path,
            difficulty=4,
            private_key_name='prv',
            password='',
        )
        self.ecc = keys_auth.ecc
        self.node_id = encode_hex(self.ecc.raw_pubkey)
        self.task_id = idgenerator.generate_id_from_hex(self.node_id)
        self.subtask_id = idgenerator.generate_id_from_hex(self.node_id)

        ts = TaskSession(Mock())
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
        ts.task_server.keys_auth = keys_auth
        self.ts = ts

        gsam = patch('golem.network.concent.helpers.history'
                     '.MessageHistoryService.get_sync_as_message',
                     Mock(side_effect=history.MessageNotFound))
        gsam.start()
        self.addCleanup(gsam.stop)

    def _prepare_report_computed_task(self, **kwargs):
        msg = msg_factories.tasks.ReportComputedTaskFactory(
            task_to_compute__task_id=self.task_id,
            task_to_compute__subtask_id=self.subtask_id,
            **kwargs,
        )
        msg._fake_sign()
        return msg

    def test_result_received(self, *_):
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

    def test_reject_result_pull_failed_no_concent(self, *_):
        msg = self._prepare_report_computed_task(
            task_to_compute__concent_enabled=False)

        with patch('golem.network.concent.helpers.history.add'):
            self.ts.task_manager.task_result_manager.pull_package = \
                self._create_pull_package(False)

        with patch('golem.task.tasksession.get_task_message', return_value=msg):
            with patch('golem.network.concent.helpers.'
                       'process_report_computed_task',
                       return_value=message.tasks.AckReportComputedTask(
                           report_computed_task=msg,
                       )):
                self.ts._react_to_report_computed_task(msg)
        self.ts.task_server.send_result_rejected.assert_called_once()
        self.ts.task_manager.task_computation_failure.assert_called_once()

    def test_reject_result_pull_failed_with_concent(self, *_):
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


@patch('golem.task.tasksession.TaskSession.disconnect')
@patch("golem.network.nodeskeeper.store")
class HelloTest(testutils.TempDirFixture):
    def setUp(self):
        super().setUp()
        self.msg = msg_factories.base.HelloFactory(
            client_key_id='deadbeef',
            node_info=dt_p2p_factory.Node(),
            proto_id=variables.PROTOCOL_CONST.ID,
        )
        addr = twisted.internet.address.IPv4Address(
            type='TCP',
            host=fake.ipv4(),
            port=fake.random_int(min=1, max=2**16-1),
        )
        conn = MagicMock(
            transport=MagicMock(
                getPeer=MagicMock(return_value=addr),
            ),
        )
        self.task_session = TaskSession(conn)
        self.task_session.task_server.config_desc.key_difficulty = 1
        self.task_session.task_server.sessions = {}

    @patch('golem.task.tasksession.TaskSession.send_hello')
    def test_positive(self, mock_hello, *_):
        self.task_session._react_to_hello(self.msg)
        mock_hello.assert_called_once_with()

    def test_react_to_hello_nodeskeeper_store(
            self,
            mock_store,
            mock_disconnect,
            *_,
    ):
        self.task_session._react_to_hello(self.msg)
        mock_store.assert_called_once_with(self.msg.node_info)
        mock_disconnect.assert_not_called()

    def test_react_to_hello_empty_node_info(
            self,
            mock_store,
            mock_disconnect,
            *_,
    ):
        self.msg.node_info = None
        self.task_session._react_to_hello(self.msg)
        mock_store.assert_not_called()
        mock_disconnect.assert_called_once_with(
            message.base.Disconnect.REASON.ProtocolVersion,
        )

    def test_react_to_hello_invalid_protocol_version(
            self,
            _mock_store,
            mock_disconnect,
            *_,
    ):
        self.msg.proto_id = -1

        # when
        with self.assertLogs(logger, level='INFO'):
            self.task_session._react_to_hello(self.msg)

        # then
        mock_disconnect.assert_called_once_with(
            message.base.Disconnect.REASON.ProtocolVersion)

    def test_react_to_hello_key_not_difficult(
            self,
            _mock_store,
            mock_disconnect,
            *_,
    ):
        # given
        self.task_session.task_server.config_desc.key_difficulty = 80

        # when
        with self.assertLogs(logger, level='INFO'):
            self.task_session._react_to_hello(self.msg)

        # then
        mock_disconnect.assert_called_with(
            message.base.Disconnect.REASON.KeyNotDifficult,
        )

    @patch('golem.task.tasksession.TaskSession.send_hello')
    def test_react_to_hello_key_difficult(self, mock_hello, *_):
        # given
        difficulty = 4
        self.task_session.task_server.config_desc.key_difficulty = difficulty
        ka = KeysAuth(datadir=self.path, difficulty=difficulty,
                      private_key_name='prv', password='')
        self.msg.client_key_id = ka.key_id

        # when
        self.task_session._react_to_hello(self.msg)
        # then
        mock_hello.assert_called_once_with()


class TestDisconnect(TestCase):
    def setUp(self):
        addr = twisted.internet.address.IPv4Address(
            type='TCP',
            host=fake.ipv4(),
            port=fake.random_int(min=1, max=2**16-1),
        )
        conn = MagicMock(
            transport=MagicMock(
                getPeer=MagicMock(return_value=addr),
            ),
        )
        self.task_session = TaskSession(conn)

    def test_unverified_without_key_id(self, *_):
        self.assertIsNone(self.task_session.key_id)
        self.assertFalse(self.task_session.verified)
        self.task_session.disconnect(
            message.base.Disconnect.REASON.NoMoreMessages,
        )


@patch('golem.task.tasksession.TaskSession._cannot_assign_task')
class TestOfferChosen(TestCase):
    def setUp(self):
        addr = twisted.internet.address.IPv4Address(
            type='TCP',
            host=fake.ipv4(),
            port=fake.random_int(min=1, max=2**16-1),
        )
        conn = MagicMock(
            transport=MagicMock(
                getPeer=MagicMock(return_value=addr),
            ),
        )
        self.task_session = TaskSession(conn)
        self.msg = msg_factories.tasks.WantToComputeTaskFactory()

    def test_ctd_is_none(self, mock_cat, *_):
        self.task_session.task_manager.get_next_subtask.return_value = None
        self.task_session._offer_chosen(
            msg=self.msg,
            node_id='deadbeef',
            is_chosen=True,
        )
        mock_cat.assert_called_once_with(
            self.msg.task_id,
            message.tasks.CannotAssignTask.REASON.NoMoreSubtasks,
        )
