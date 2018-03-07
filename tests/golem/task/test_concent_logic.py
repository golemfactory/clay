"""Tests related to Concent integration.

Documentation:
https://docs.google.com/document/d/1QMnamlNnKxichfPZvBDIcFm1q0uJHMHJPkCt24KElxc/
"""
import calendar
import datetime
import unittest.mock as mock

from freezegun import freeze_time
from golem_messages.message import concents

from golem import testutils
from golem.core import keysauth
from golem.network import history
from golem.task import taskbase
from golem.task import tasksession
from golem.task import taskstate
from tests import factories


reject_reasons = concents.RejectReportComputedTask.REASON

# pylint: disable=protected-access


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
        self.msg = factories.messages.ReportComputedTask()
        self.now = datetime.datetime.utcnow()
        now_ts = calendar.timegm(self.now.utctimetuple())
        self.msg.task_to_compute.compute_task_def['deadline'] = now_ts + 60
        self.msg.task_to_compute.sig = keys_auth.ecc.sign(
            inputb=self.msg.task_to_compute.get_short_hash(),
        )
        task_id = self.msg.task_to_compute.compute_task_def['task_id']
        task_header = taskbase.TaskHeader(*(None,)*6)
        task_header.deadline = now_ts + 3600
        self.task_session.task_server.task_keeper.task_headers = {
            task_id: task_header,
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
        self.assertIsInstance(msg, concents.RejectReportComputedTask)
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

    @mock.patch('golem.task.tasksession.TaskSession.send')
    def test_task_deadline(self, send_mock):
        "Reject after task timeout"
        after_deadline = self.now \
            + datetime.timedelta(hours=1, seconds=1)
        with freeze_time(after_deadline):
            self.task_session._react_to_report_computed_task(self.msg)
        self.assert_reject_reason(
            send_mock,
            reject_reasons.TaskTimeLimitExceeded,
        )

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
        self.assertIsInstance(ack_msg, concents.AckReportComputedTask)

    @mock.patch('golem.network.history.MessageHistoryService.get_sync')
    @mock.patch('golem.task.tasksession.TaskSession.send')
    def test_subtask_deadline(self, send_mock, get_mock):
        "Reject after subtask timeout"
        get_mock.return_value = []
        after_deadline = self.now \
            + datetime.timedelta(minutes=1, seconds=1)
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
            factories.messages.CannotComputeTask(
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
        unwanted_msg = factories.messages.TaskFailure(
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
        self.assertIsInstance(ack_msg, concents.AckReportComputedTask)
        self.assertEqual(ack_msg.subtask_id, self.msg.subtask_id)
        self.assertEqual(ack_msg.task_to_compute, self.msg.task_to_compute)
