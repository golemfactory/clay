"""Tests related to Concent integration.

Documentation:
https://docs.google.com/document/d/1QMnamlNnKxichfPZvBDIcFm1q0uJHMHJPkCt24KElxc/
"""
import calendar
import datetime
import unittest
import unittest.mock as mock

from freezegun import freeze_time
from golem_messages import constants as msg_constants
from golem_messages import cryptography
from golem_messages import factories
from golem_messages import message
from golem_messages.utils import encode_hex

from golem import testutils
from golem.core import keysauth
from golem.network import history
from golem.task import taskbase
from golem.task import tasksession
from golem.task import taskstate

from tests.factories.p2p import Node

reject_reasons = message.tasks.RejectReportComputedTask.REASON
cannot_reasons = message.tasks.CannotComputeTask.REASON

# pylint: disable=protected-access


@mock.patch("golem.task.tasksession.TaskSession._check_ctd_params",
            return_value=True)
@mock.patch("golem.task.tasksession.TaskSession.send")
class TaskToComputeConcentTestCase(testutils.TempDirFixture):
    def setUp(self):
        super().setUp()
        self.msg = factories.tasks.TaskToComputeFactory()
        self.task_session = tasksession.TaskSession(mock.MagicMock())
        self.task_session.task_server.task_keeper\
            .task_headers[self.msg.task_id]\
            .subtasks_count = 10
        self.task_session.task_server.client.transaction_system\
            .get_available_gnt.return_value = self.msg.price * 10
        self.task_session.task_server.client.transaction_system\
            .concent_balance.return_value = (self.msg.price * 10) * 2
        self.task_session.task_server.client.transaction_system\
            .concent_timelock.return_value = 0

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

    def test_requestor_failed_to_concent(self, send_mock, *_):
        self.task_session.concent_service.enabled = True
        self.msg.concent_enabled = False
        self.task_session._react_to_task_to_compute(self.msg)
        self.assert_rejected(send_mock)

    def test_requestor_concented(self, send_mock, *_):
        self.task_session.concent_service.enabled = True
        self.msg.concent_enabled = True
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
        self.msg.concent_enabled = True
        self.task_session._react_to_task_to_compute(self.msg)
        self.assert_rejected(
            send_mock,
            reason=cannot_reasons.ConcentDisabled,
        )

    def test_requestor_low_balance(self, send_mock, *_):
        self.task_session.concent_service.enabled = True
        self.msg.concent_enabled = True
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
        self.task_session.concent_service.enabled = True
        self.msg.concent_enabled = True
        self.task_session.task_server.client.transaction_system\
            .concent_balance.return_value = int((self.msg.price * 10) * 1.5)
        self.task_session._react_to_task_to_compute(self.msg)
        self.assert_rejected(
            send_mock,
            reason=cannot_reasons.InsufficientDeposit,
        )

    def test_requestor_short_deposit(self, send_mock, *_):
        self.task_session.concent_service.enabled = True
        self.msg.concent_enabled = True
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
        self.task_session.key_id = "KEY_ID"
        self.msg = factories.tasks.ReportComputedTaskFactory()
        self.now = datetime.datetime.utcnow()
        now_ts = calendar.timegm(self.now.utctimetuple())
        self.msg.task_to_compute.compute_task_def['deadline'] = now_ts + 60
        self.msg.task_to_compute.sig = keys_auth.ecc.sign(
            inputb=self.msg.task_to_compute.get_short_hash(),
        )
        task_id = self.msg.task_to_compute.compute_task_def['task_id']
        task_header = taskbase.TaskHeader(
            task_id='task_id',
            environment='env',
            task_owner=Node()
        )
        task_header.deadline = now_ts + 3600
        task = mock.Mock()
        task.header = task_header
        self.task_session.task_manager.tasks = {
            task_id: task,
        }
        self.task_session.task_manager.tasks_states = {}
        self.task_session.task_manager.tasks_states[task_id] = task_state = \
            taskstate.TaskState()
        ctk = self.task_session.task_manager.comp_task_keeper
        ctk.get_node_for_task_id.return_value = "KEY_ID"
        self.task_session.task_manager.get_node_id_for_subtask.return_value = \
            "KEY_ID"
        task_state.subtask_states[self.msg.subtask_id] = subtask_state = \
            taskstate.SubtaskState()
        subtask_state.deadline = self.msg.task_to_compute.compute_task_def[
            'deadline'
        ]

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
    def test_subtask_id_unknown(self, dropped_mock):
        "Drop if subtask is unknown"
        self.task_session.task_manager.get_node_id_for_subtask.return_value = \
            None
        self.task_session._react_to_report_computed_task(self.msg)
        dropped_mock.assert_called_once_with()
        self.task_session.task_manager.get_node_id_for_subtask.return_value = \
            "KEY_ID"

    @mock.patch('golem.task.tasksession.TaskSession.dropped')
    def test_no_task_to_compute(self, dropped_mock):
        "Drop if task_to_compute is absent"
        self.msg.task_to_compute = None
        self.task_session._react_to_report_computed_task(self.msg)
        dropped_mock.assert_called_once_with()

    @mock.patch('golem.task.tasksession.TaskSession.dropped')
    def test_spoofed_task_to_compute(self, dropped_mock):
        "Drop if task_to_compute is spoofed"
        self.msg.task_to_compute.sig = '31337'
        self.task_session._react_to_report_computed_task(self.msg)
        dropped_mock.assert_called_once_with()

    @mock.patch('golem.network.history.MessageHistoryService.get_sync')
    @mock.patch('golem.task.tasksession.TaskSession.send')
    def test_task_deadline_not_found(self, send_mock, get_mock):
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
    def test_subtask_deadline(self, send_mock, get_mock):
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
    def test_cannot_compute_task_received(self, send_mock, get_mock):
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
    def test_task_failure_received(self, send_mock):
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


@mock.patch('golem.task.tasksession.TaskSession.send')
class ReactToWantToComputeTaskTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.requestor_keys = cryptography.ECCx(None)
        self.msg = factories.tasks.WantToComputeTaskFactory()
        self.task_session = tasksession.TaskSession(mock.MagicMock())
        self.task_session.task_server.keys_auth.ecc = self.requestor_keys

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
        task_manager = self.task_session.task_manager
        self.msg.concent_enabled = None
        task_session = self.task_session
        task_session.concent_service.enabled = False
        task_manager = task_session.task_manager
        task_manager.check_next_subtask.return_value = True
        task_manager.is_my_task.return_value = True
        task_manager.should_wait_for_node.return_value = False
        ctd = factories.tasks.ComputeTaskDefFactory()
        task_manager.get_next_subtask.return_value = ctd


        task = mock.MagicMock()
        task_state = mock.MagicMock(package_hash='123', package_size=42)
        task.header.task_owner.key = encode_hex(self.requestor_keys.raw_pubkey)
        task_manager.tasks = {ctd['task_id']: task}
        task_manager.tasks_states = {ctd['task_id']: task_state}

        with mock.patch(
            'golem.task.tasksession.taskkeeper.compute_subtask_value',
            mock.Mock(return_value=667),
        ):
            task_session._react_to_want_to_compute_task(self.msg)

        send_mock.assert_called()
        ttc = send_mock.call_args_list[2][0][0]
        self.assertIsInstance(ttc, message.tasks.TaskToCompute)
        self.assertFalse(ttc.concent_enabled)
