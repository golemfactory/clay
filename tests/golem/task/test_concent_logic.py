"""Tests related to Concent integration.

Documentation:
https://docs.google.com/document/d/1QMnamlNnKxichfPZvBDIcFm1q0uJHMHJPkCt24KElxc/
"""
import calendar
import datetime
import unittest.mock as mock

from apps import appsmanager

from freezegun import freeze_time
from golem_messages import constants as msg_constants
from golem_messages import cryptography
from golem_messages import factories
from golem_messages import message
from golem_messages.factories.datastructures import tasks as dt_tasks_factory
from golem_messages.utils import encode_hex

from golem import testutils
from golem.config.active import EthereumConfig
from golem.core import keysauth
from golem.marketplace import RequestorBrassMarketStrategy
from golem.network import history
from golem.task import tasksession
from golem.task import taskstate
from golem.tools.testwithreactor import TestWithReactor

from tests.factories.task import taskstate as taskstate_factory

reject_reasons = message.tasks.RejectReportComputedTask.REASON
cannot_reasons = message.tasks.CannotComputeTask.REASON

# pylint: disable=protected-access


def _fake_get_efficacy():
    class A:
        def __init__(self):
            self.vector = (.0, .0, .0, .0)
    return A()


def _call_in_place(_delay, fn, *args, **kwargs):
    return fn(*args, **kwargs)


@mock.patch("golem.task.tasksession.TaskSession._check_task_header",
            return_value=True)
@mock.patch("golem.task.tasksession.TaskSession.send")
class TaskToComputeConcentTestCase(testutils.TempDirFixture):
    def setUp(self):
        super().setUp()
        self.wtct_price = 100
        self.subtasks_count = 10
        self.keys = cryptography.ECCx(None)
        self.different_keys = cryptography.ECCx(None)
        self.requestor_keys = cryptography.ECCx(None)
        self.msg: message.tasks.TaskToCompute = \
            factories.tasks.TaskToComputeFactory(
                requestor_ethereum_public_key=encode_hex(
                    self.requestor_keys.raw_pubkey),
                want_to_compute_task__task_header__subtasks_count=self.subtasks_count,  # noqa pylint:disable=line-too-long
                want_to_compute_task__task_header__max_price=self.wtct_price,
                want_to_compute_task__task_header__subtask_timeout=360,
                want_to_compute_task__price=self.wtct_price,
                price=self.wtct_price // 10,
            )
        self.msg.concent_enabled = True
        self.msg.want_to_compute_task.sign_message(self.keys.raw_privkey)  # noqa pylint: disable=no-member
        self.msg.generate_ethsig(self.requestor_keys.raw_privkey)
        self.ethereum_config = EthereumConfig()
        self.msg.sign_all_promissory_notes(
            deposit_contract_address=self.ethereum_config.
            deposit_contract_address,
            private_key=self.requestor_keys.raw_privkey
        )
        self.msg.sign_message(self.requestor_keys.raw_privkey)  # noqa go home pylint, you're drunk pylint: disable=no-value-for-parameter
        self.task_session = tasksession.TaskSession(mock.MagicMock())

        self.task_session.task_server.client\
            .transaction_system.deposit_contract_address = \
            self.ethereum_config.deposit_contract_address

        self.task_session.concent_service.enabled = True
        self.task_session.concent_service.required_as_provider = True
        self.task_session.task_computer.has_assigned_task.return_value = False
        self.task_session.task_server.keys_auth.ecc.raw_pubkey = \
            self.keys.raw_pubkey
        self.task_session.task_server.config_desc.max_resource_size = \
            1024 * 1024 * 1024 * 100
        self.task_session.task_server.task_keeper\
            .task_headers[self.msg.task_id]\
            .subtasks_count = 10
        self.task_session.task_server.client.transaction_system\
            .get_available_gnt.return_value = self.msg.price * 10
        self.task_session.task_server.client.transaction_system\
            .concent_balance.return_value = (self.msg.price * 10) * 2
        self.task_session.task_server.client.transaction_system\
            .concent_timelock.return_value = 0
        self.task_session.task_manager.task_finished.return_value = False

    def assert_accepted(self, send_mock):  # pylint: disable=no-self-use
        send_mock.assert_not_called()

    def assert_rejected(
            self,
            send_mock,
            reason=cannot_reasons.ConcentRequired):
        send_mock.assert_called_once_with(mock.ANY)
        msg = send_mock.call_args[0][0]
        self.assertIsInstance(msg, message.tasks.CannotComputeTask)
        self.assertIs(
            msg.reason,
            reason,
        )

    def test_requestor_concented(self, send_mock, *_):
        self.task_session._react_to_task_to_compute(self.msg)
        self.assert_accepted(send_mock)

    def test_requestor_failed_to_concent(self, send_mock, *_):
        self.msg.concent_enabled = False
        self.task_session._react_to_task_to_compute(self.msg)
        self.assert_rejected(send_mock)

    def test_requestor_concent_disabled_but_not_required(self, send_mock, *_):
        self.msg.concent_enabled = False
        self.task_session.concent_service.required_as_provider = False
        self.task_session._react_to_task_to_compute(self.msg)
        self.assert_accepted(send_mock)

    def test_provider_doesnt_want_concent(self, send_mock, *_):
        self.task_session.concent_service.enabled = False
        self.msg.concent_enabled = False
        self.task_session._react_to_task_to_compute(self.msg)
        self.assert_accepted(send_mock)

    def test_provider_doesnt_want_concent_but_requestor_insists(
            self,
            send_mock,
            *_):
        self.task_session.concent_service.enabled = False
        self.task_session._react_to_task_to_compute(self.msg)
        self.assert_rejected(
            send_mock,
            reason=cannot_reasons.ConcentDisabled,
        )

    def test_requestor_low_balance(self, send_mock, *_):
        self.task_session.task_server.client.transaction_system\
            .get_available_gnt.return_value = self.msg.price * 9
        self.task_session._react_to_task_to_compute(self.msg)
        self.assert_rejected(
            send_mock,
            reason=cannot_reasons.InsufficientBalance,
        )

    def test_requestor_low_balance_no_concent(
            self,
            send_mock,
            *_):
        self.task_session.task_server.client.transaction_system\
            .get_available_gnt.return_value = self.msg.price * 9
        self.task_session.concent_service.enabled = False
        self.msg.concent_enabled = False
        self.task_session._react_to_task_to_compute(self.msg)
        self.assert_rejected(
            send_mock,
            reason=cannot_reasons.InsufficientBalance,
        )

    def test_requestor_low_deposit(self, send_mock, *_):
        self.task_session.task_server.client.transaction_system\
            .concent_balance.return_value = int((self.msg.price * 10) * 1.5)
        self.task_session._react_to_task_to_compute(self.msg)
        self.assert_rejected(
            send_mock,
            reason=cannot_reasons.InsufficientDeposit,
        )

    def test_requestor_short_deposit(self, send_mock, *_):
        self.task_session.task_server.client.transaction_system\
            .concent_timelock.return_value = 1
        self.task_session._react_to_task_to_compute(self.msg)
        self.assert_rejected(
            send_mock,
            reason=cannot_reasons.TooShortDeposit,
        )

    def test_requestor_low_short_deposit_no_concent(
            self,
            send_mock,
            *_):
        self.task_session.concent_service.enabled = False
        self.msg.concent_enabled = False
        self.task_session.task_server.client.transaction_system\
            .concent_balance.return_value = int((self.msg.price * 10) * 1.5)
        self.task_session.task_server.client.transaction_system\
            .concent_timelock.return_value = 1
        self.task_session._react_to_task_to_compute(self.msg)
        self.assert_accepted(send_mock)

    def test_want_to_compute_task_signed_by_different_key_than_it_contains(
            self,
            send_mock,
            *_):
        self.msg = factories.tasks.TaskToComputeFactory()
        self.msg._fake_sign()
        self.msg.want_to_compute_task.sign_message(  # pylint: disable=no-member
            self.different_keys.raw_privkey)
        with mock.patch(
            'golem.task.tasksession.TaskSession.dropped'
        ) as task_session_dropped:
            self.task_session._react_to_task_to_compute(self.msg)
        send_mock.assert_not_called()
        task_session_dropped.assert_called_once()

    def test_no_promissory_note_sig(self, send_mock, *_):
        self.msg.promissory_note_sig = None
        self.task_session._react_to_task_to_compute(self.msg)
        self.assert_rejected(
            send_mock,
            reason=cannot_reasons.PromissoryNoteMissing,
        )

    def test_no_concent_promissory_note_sig(self, send_mock, *_):
        self.msg.concent_promissory_note_sig = None
        self.task_session._react_to_task_to_compute(self.msg)
        self.assert_rejected(
            send_mock,
            reason=cannot_reasons.PromissoryNoteMissing,
        )

    def test_bad_promissory_note_sig(self, send_mock, *_):
        self.msg.sign_promissory_note(
            deposit_contract_address=self.ethereum_config.
            deposit_contract_address,
            private_key=self.different_keys.raw_privkey
        )
        self.task_session._react_to_task_to_compute(self.msg)
        self.assert_rejected(
            send_mock,
            reason=cannot_reasons.PromissoryNoteMissing,
        )

    def test_bad_concent_promissory_note_sig(self, send_mock, *_):
        self.msg.sign_concent_promissory_note(
            deposit_contract_address=self.ethereum_config.
            deposit_contract_address,
            private_key=self.different_keys.raw_privkey
        )
        self.task_session._react_to_task_to_compute(self.msg)
        self.assert_rejected(
            send_mock,
            reason=cannot_reasons.PromissoryNoteMissing,
        )


@mock.patch(
    'golem.task.tasksession.TaskSession.verify_owners',
    return_value=True,
)
class ReactToReportComputedTaskTestCase(testutils.TempDirFixture):
    def setUp(self):
        super().setUp()
        self.task_session = tasksession.TaskSession(mock.MagicMock())
        self.task_session.task_server.keys_auth = keys_auth = \
            keysauth.KeysAuth(
                datadir=self.tempdir,
                private_key_name='priv_key',
                password='password',
            )
        self.task_session.key_id = "deadbeef"
        self.msg = factories.tasks.ReportComputedTaskFactory()
        self.msg._fake_sign()
        self.now = datetime.datetime.utcnow()
        now_ts = calendar.timegm(self.now.utctimetuple())
        self.msg.task_to_compute.compute_task_def['deadline'] = now_ts + 60
        self.msg.task_to_compute.sig = keys_auth.ecc.sign(
            inputb=self.msg.task_to_compute.get_short_hash(),
        )
        task_id = self.msg.task_to_compute.compute_task_def['task_id']
        task_header = dt_tasks_factory.TaskHeaderFactory()
        task_header.deadline = now_ts + 3600
        task = mock.Mock()
        task.header = task_header
        self.task_session.task_manager.task_finished.return_value = False
        self.task_session.task_manager.tasks = {
            task_id: task,
        }
        self.task_session.task_manager.tasks_states = {}
        self.task_session.task_manager.tasks_states[task_id] = task_state = \
            taskstate.TaskState()
        self.task_session.requested_task_manager.get_node_id_for_subtask.\
            return_value = None
        ctk = self.task_session.task_manager.comp_task_keeper
        ctk.get_node_for_task_id.return_value = self.task_session.key_id
        self.task_session.task_manager.get_node_id_for_subtask.return_value = \
            self.task_session.key_id
        task_state.subtask_states[self.msg.subtask_id] =\
            taskstate_factory.SubtaskState(
                deadline=self.msg.task_to_compute.compute_task_def[
                    'deadline'
                ],
            )

    def assert_reject_reason(self, send_mock, reason, **kwargs):
        send_mock.assert_called_once_with(mock.ANY)
        msg = send_mock.call_args[0][0]
        self.assertIsInstance(msg, message.tasks.RejectReportComputedTask)
        self.assertEqual(msg.subtask_id, self.msg.subtask_id)
        self.assertEqual(msg.task_to_compute, self.msg.task_to_compute)
        self.assertEqual(msg.reason, reason)
        for attr_name in kwargs:
            self.assertEqual(getattr(msg, attr_name), kwargs[attr_name])

    @mock.patch('golem.task.tasksession.TaskSession.dropped')
    def test_subtask_id_unknown(self, dropped_mock, *_):
        "Drop if subtask is unknown"
        self.task_session.task_manager.get_node_id_for_subtask.return_value = \
            None
        self.task_session._react_to_report_computed_task(self.msg)
        dropped_mock.assert_called_once_with()

    @mock.patch('golem.task.tasksession.TaskSession.send')
    def test_spoofed_task_to_compute(self, send_mock, verify_mock, *_):
        "Drop if task_to_compute is spoofed"
        verify_mock.return_value = False
        self.task_session._react_to_report_computed_task(self.msg)
        send_mock.assert_not_called()

    @mock.patch('golem.network.history.MessageHistoryService.get_sync')
    @mock.patch('golem.task.tasksession.TaskSession.send')
    def test_task_deadline_not_found(self, send_mock, get_mock, *_):
        "Reject if subtask timeout unreachable"
        get_mock.return_value = []
        self.task_session.task_server.task_keeper.task_headers = {}
        self.task_session._react_to_report_computed_task(self.msg)
        self.assertEqual(send_mock.call_count, 1)
        concent_call = send_mock.call_args_list[0]
        ack_msg = concent_call[0][0]
        self.assertIsInstance(ack_msg, message.tasks.AckReportComputedTask)

    @mock.patch('golem.network.history.MessageHistoryService.get_sync')
    @mock.patch('golem.task.tasksession.TaskSession.send')
    def test_subtask_deadline(self, send_mock, get_mock, *_):
        "Reject after subtask timeout"
        get_mock.return_value = []
        after_deadline = self.now \
            + datetime.timedelta(minutes=1, seconds=1) \
            + (msg_constants.MTD * 2)  # TOLERANCE
        with freeze_time(after_deadline):
            self.task_session._react_to_report_computed_task(self.msg)
        self.assert_reject_reason(
            send_mock,
            reject_reasons.SubtaskTimeLimitExceeded,
        )

    @mock.patch(
        'golem.network.history.MessageHistoryService.get_sync_as_message'
    )
    @mock.patch('golem.task.tasksession.TaskSession.send')
    def test_cannot_compute_task_received(self, send_mock, get_mock, *_):
        "Reject if CannotComputeTask received"
        get_mock.return_value = unwanted_msg = \
            factories.tasks.CannotComputeTaskFactory(
                subtask_id=self.msg.subtask_id,
                task_to_compute=self.msg.task_to_compute,
            )
        self.task_session._react_to_report_computed_task(self.msg)
        self.assert_reject_reason(
            send_mock,
            reject_reasons.GotMessageCannotComputeTask,
            cannot_compute_task=unwanted_msg,
        )

    @mock.patch('golem.task.tasksession.TaskSession.send')
    def test_task_failure_received(self, send_mock, *_):
        "Reject if TaskFailure received"
        unwanted_msg = factories.tasks.TaskFailureFactory(
            subtask_id=self.msg.subtask_id,
            task_to_compute=self.msg.task_to_compute,
        )

        def get_wrap(msg_cls, **_):
            if msg_cls == 'TaskFailure':
                return unwanted_msg
            raise history.MessageNotFound

        with mock.patch(
            'golem.network.history.MessageHistoryService.get_sync_as_message',
            wraps=get_wrap,
        ):
            self.task_session._react_to_report_computed_task(self.msg)
        self.assert_reject_reason(
            send_mock,
            reject_reasons.GotMessageTaskFailure,
            task_failure=unwanted_msg,
        )

    @mock.patch(
        'golem.network.history.MessageHistoryService.get_sync_as_message',
        side_effect=history.MessageNotFound,
    )
    @mock.patch('golem.task.tasksession.TaskSession.send')
    def test_ack(self, send_mock, *_):
        "Send ACK if verification passed"
        self.task_session._react_to_report_computed_task(self.msg)
        self.assertEqual(send_mock.call_count, 1)
        concent_call = send_mock.call_args_list[0]
        ack_msg = concent_call[0][0]
        self.assertIsInstance(ack_msg, message.tasks.AckReportComputedTask)
        self.assertEqual(ack_msg.subtask_id, self.msg.subtask_id)
        self.assertEqual(ack_msg.report_computed_task, self.msg)


@mock.patch('golem.core.deferred.call_later', _call_in_place)
@mock.patch('golem.ranking.manager.database_manager.get_provider_efficiency',
            mock.Mock(return_value=0.0))
@mock.patch('golem.ranking.manager.database_manager.get_provider_efficacy',
            mock.Mock(return_value=_fake_get_efficacy()))
@mock.patch(
    'golem.task.tasksession.TaskSession.send',
    side_effect=lambda msg: msg._fake_sign(),
)
class ReactToWantToComputeTaskTestCase(TestWithReactor):
    def setUp(self):
        super().setUp()
        self.requestor_keys = cryptography.ECCx(None)
        self.msg = factories.tasks.WantToComputeTaskFactory(
            price=10 ** 18,
            cpu_usage=int(1e9),
            task_header__environment='BLENDER',
        )
        self.msg.task_header.sign(self.requestor_keys.raw_privkey)
        self.msg._fake_sign()
        self.task_session = tasksession.TaskSession(mock.MagicMock())
        self.task_session.key_id = 'unittest_key_id'
        self.task_session.task_server.keys_auth._private_key = \
            self.requestor_keys.raw_privkey
        self.task_session.task_server.keys_auth.public_key = \
            self.requestor_keys.raw_pubkey
        self.task_session.task_manager.task_finished.return_value = False
        self.task_session.requested_task_manager.task_exists.return_value = \
            False

        apps_manager = appsmanager.AppsManager()
        apps_manager.load_all_apps()
        self.task_session.task_server.client.apps_manager = apps_manager

    def assert_blocked(self, send_mock):
        self.task_session._react_to_want_to_compute_task(self.msg)
        cat_msg = send_mock.call_args_list[0][0][0]
        self.assertIsInstance(cat_msg, message.tasks.CannotAssignTask)
        self.assertIs(
            cat_msg.reason,
            message.tasks.CannotAssignTask.REASON.ConcentDisabled,
        )
        self.task_session.task_manager.got_want_to_compute.assert_not_called()

    def assert_allowed(self, send_mock):
        task_manager = self.task_session.task_manager
        task_manager.is_my_task.return_value = True
        task_manager.should_wait_for_node.return_value = False
        task_manager.check_next_subtask.return_value = False
        self.task_session._react_to_want_to_compute_task(self.msg)
        send_mock.assert_called()
        # ctd, wrong_task, wait
        self.task_session.task_manager.check_next_subtask.assert_called_once()

    def test_provider_with_concent_requestor_without_concent(
            self, send_mock):
        self.msg.concent_enabled = True
        self.task_session.concent_service.enabled = False
        self.assert_blocked(send_mock)

    def test_provider_with_concent_requestor_with_concent(
            self, send_mock):
        self.msg.concent_enabled = True
        self.task_session.concent_service.enabled = True
        self.assert_allowed(send_mock)

    def test_provider_without_concent_requestor_without_concent(
            self, send_mock):
        self.msg.concent_enabled = False
        self.task_session.concent_service.enabled = False
        self.assert_allowed(send_mock)

    def test_provider_without_concent_requestor_with_concent(
            self, send_mock):
        self.msg.concent_enabled = False
        self.task_session.concent_service.enabled = True
        self.assert_allowed(send_mock)

    def test_concent_disabled_wtct_concent_flag_none(self, send_mock):
        self.msg.concent_enabled = None
        task_session = self.task_session
        task_session.concent_service.enabled = False
        task_manager = task_session.task_manager
        task_manager.check_next_subtask.return_value = True
        task_manager.is_my_task.return_value = True
        task_manager.should_wait_for_node.return_value = False
        ctd = factories.tasks.ComputeTaskDefFactory(task_id=self.msg.task_id)
        ctd["resources"] = []
        task_manager.get_next_subtask.return_value = ctd

        task = mock.MagicMock()
        task.REQUESTOR_MARKET_STRATEGY = RequestorBrassMarketStrategy
        task_state = mock.MagicMock(package_hash='123', package_size=42)
        task.header.task_owner.key = encode_hex(self.requestor_keys.raw_pubkey)
        task.header.max_price = 0
        task_manager.tasks = {ctd['task_id']: task}
        task_manager.tasks_states = {ctd['task_id']: task_state}

        class X:
            pass

        task_session.task_server.get_share_options.return_value = X()
        task_session.task_server.get_resources.return_value = []
        task_session.task_server.config_desc.offer_pooling_interval = 0

        with mock.patch(
            'golem.task.tasksession.calculate_subtask_payment',
            mock.Mock(return_value=667),
        ):
            task_session._react_to_want_to_compute_task(self.msg)

        send_mock.assert_called()
        ttc = send_mock.call_args_list[0][0][0]
        self.assertIsInstance(ttc, message.tasks.TaskToCompute)
        self.assertFalse(ttc.concent_enabled)
