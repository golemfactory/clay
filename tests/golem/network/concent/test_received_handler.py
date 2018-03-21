# pylint: disable=protected-access
import gc
import importlib
import unittest
import unittest.mock as mock

from golem_messages import exceptions as msg_exceptions
from golem_messages import message

from golem import testutils
from golem.model import Actor
from golem.network import history
from golem.network.concent import received_handler
from golem.network.concent.handlers_library import library
from tests.factories import messages as msg_factories
from tests.factories import taskserver as taskserver_factories


class RegisterHandlersTestCase(unittest.TestCase):
    def setUp(self):
        library._handlers = {}

    def test_register_handlers(self):
        class MyHandler():
            def not_a_handler(self, msg):
                pass

            @received_handler.handler_for(message.p2p.Ping)
            def ping_handler(self, msg):
                pass

        instance = MyHandler()
        received_handler.register_handlers(instance)
        self.assertEqual(len(library._handlers), 1)
        self.assertEqual(
            library._handlers[message.p2p.Ping](),
            instance.ping_handler,
        )


@mock.patch("golem.network.history.add")
class TestOnForceReportComputedTaskResponse(unittest.TestCase):
    def setUp(self):
        self.msg = msg_factories.ForceReportComputedTaskResponse()
        self.reasons = message.concents.ForceReportComputedTaskResponse.REASON
        ttc = self.msg.ack_report_computed_task.task_to_compute
        self.call_response = mock.call(
            msg=self.msg,
            node_id=ttc.requestor_id,
            local_role=Actor.Provider,
            remote_role=Actor.Concent,
        )
        importlib.reload(received_handler)

    def tearDown(self):
        library._handlers = {}

    def test_subtask_timeout(self, add_mock):
        self.msg.ack_report_computed_task = None
        self.msg.reject_report_computed_task = None
        self.msg.reason = self.reasons.SubtaskTimeout
        library.interpret(self.msg)
        add_mock.assert_called_once_with(
            msg=self.msg,
            node_id=None,
            local_role=Actor.Provider,
            remote_role=Actor.Concent,
        )

    def test_concent_ack(self, add_mock):
        self.msg.reason = self.reasons.ConcentAck
        self.msg.reject_report_computed_task = None
        library.interpret(self.msg)
        ttc = self.msg.ack_report_computed_task.task_to_compute
        call_inner = mock.call(
            msg=self.msg.ack_report_computed_task,
            node_id=ttc.requestor_id,
            local_role=Actor.Provider,
            remote_role=Actor.Concent,
        )
        self.assertEqual(add_mock.call_count, 2)
        add_mock.assert_has_calls([
            self.call_response,
            call_inner,
        ])

    def test_ack_from_requestor(self, add_mock):
        self.msg.reason = self.reasons.AckFromRequestor
        self.msg.reject_report_computed_task = None
        library.interpret(self.msg)
        ttc = self.msg.ack_report_computed_task.task_to_compute
        self.assertEqual(add_mock.call_count, 2)
        call_inner = mock.call(
            msg=self.msg.ack_report_computed_task,
            node_id=ttc.requestor_id,
            local_role=Actor.Provider,
            remote_role=Actor.Requestor,
        )
        add_mock.assert_has_calls([
            self.call_response,
            call_inner,
        ])

    def test_reject_from_requestor(self, add_mock):
        self.msg.reason = self.reasons.RejectFromRequestor
        self.msg.ack_report_computed_task = None
        library.interpret(self.msg)
        ttc = self.msg.reject_report_computed_task.task_to_compute
        self.assertEqual(add_mock.call_count, 2)
        call_inner = mock.call(
            msg=self.msg.reject_report_computed_task,
            node_id=ttc.requestor_id,
            local_role=Actor.Provider,
            remote_role=Actor.Requestor,
        )
        add_mock.assert_has_calls([
            self.call_response,
            call_inner,
        ])


# pylint: disable=no-self-use
class TaskServerMessageHandlerTestCase(
        testutils.DatabaseFixture, testutils.TestWithClient):
    def setUp(self):
        for parent in self.__class__.__bases__:
            parent.setUp(self)
        self.task_server = taskserver_factories.TaskServer(
            client=self.client,
        )
        history.MessageHistoryService()
        # received_handler.TaskServerMessageHandler is instantiated
        # in TaskServer.__init__

        self.cf_transfer = self.client.concent_filetransfers.transfer


    def tearDown(self):
        # Remove registered handlers
        del self.task_server
        gc.collect()

    @mock.patch("golem.network.concent.received_handler.logger.warning")
    def test_concent_service_refused(self, logger_mock):
        msg = msg_factories.ServiceRefused()
        library.interpret(msg)
        self.assertIn('Concent service (%s) refused',
                      logger_mock.call_args[0][0])

    @mock.patch("golem.task.taskserver.TaskServer"
                ".receive_subtask_computation_time")
    def test_verdict_report_computed_task(
            self,
            rsct_mock):
        msg = msg_factories.VerdictReportComputedTask()
        library.interpret(msg)
        self.assertEqual(
            self.client.keys_auth.ecc.verify.call_count,
            2,
        )
        rct = msg.force_report_computed_task.report_computed_task
        rsct_mock.assert_called_once_with(
            msg.ack_report_computed_task.subtask_id,
            rct.computation_time,
        )

    @mock.patch("golem.task.taskserver.TaskServer"
                ".receive_subtask_computation_time")
    @mock.patch("golem.task.taskserver.TaskServer.get_result")
    def test_verdict_report_computed_task_invalid_sig(
            self,
            get_mock,
            rsct_mock):
        self.client.keys_auth.ecc.verify.side_effect = \
            msg_exceptions.InvalidSignature
        msg = msg_factories.VerdictReportComputedTask()
        library.interpret(msg)
        ttc_from_ack = msg.ack_report_computed_task.task_to_compute
        self.client.keys_auth.ecc.verify.assert_called_once_with(
            inputb=ttc_from_ack.get_short_hash(),
            sig=ttc_from_ack.sig)
        rsct_mock.assert_not_called()
        get_mock.assert_not_called()

    @mock.patch("golem.task.taskserver.TaskServer"
                ".receive_subtask_computation_time")
    @mock.patch("golem.task.taskserver.TaskServer.get_result")
    def test_verdict_report_computed_task_diff_ttc(
            self,
            get_mock,
            rsct_mock):
        msg = msg_factories.VerdictReportComputedTask()
        msg.ack_report_computed_task.task_to_compute = \
            msg_factories.TaskToCompute()
        self.assertNotEqual(
            msg.ack_report_computed_task.task_to_compute,
            msg.force_report_computed_task.report_computed_task.task_to_compute,
        )
        library.interpret(msg)
        rsct_mock.assert_not_called()
        get_mock.assert_not_called()

    @mock.patch(
        "golem.network.concent.helpers.process_report_computed_task"
    )
    def test_force_report_computed_task(self, helper_mock):
        msg = msg_factories.ForceReportComputedTask()
        helper_mock.return_value = returned_msg = object()
        library.interpret(msg)
        helper_mock.assert_called_once_with(
            msg=msg.report_computed_task,
            ecc=mock.ANY,
            task_header_keeper=mock.ANY,
        )
        self.task_server.client.concent_service.submit_task_message \
            .assert_called_once_with(
                msg.report_computed_task.subtask_id,
                returned_msg)

    @mock.patch('golem.task.taskmanager.TaskManager.task_computation_failure')
    def test_force_get_task_result_failed(self, tcf):
        fgtrf = msg_factories.ForceGetTaskResultFailed()
        library.interpret(fgtrf)

        msg = history.MessageHistoryService.get_sync_as_message(
            task=fgtrf.task_id,
            subtask=fgtrf.subtask_id,
            node=fgtrf.task_to_compute.provider_id,
            msg_cls='ForceGetTaskResultFailed',
        )

        self.assertIsInstance(msg, message.concents.ForceGetTaskResultFailed)
        tcf.assert_called_once_with(
            fgtrf.subtask_id,
            'Error downloading the task result through the Concent')

    def test_force_subtask_results_response_empty(self):
        msg = message.concents.ForceSubtaskResultsResponse()
        # pylint: disable=no-member
        self.assertIsNone(msg.subtask_results_accepted)
        self.assertIsNone(msg.subtask_results_rejected)
        # pylint: enable=no-member
        with self.assertRaises(RuntimeError):
            library.interpret(msg)

    @mock.patch("golem.network.history.add")
    @mock.patch("golem.task.taskserver.TaskServer.subtask_accepted")
    def test_force_subtask_results_response_accepted(
            self,
            accepted_mock,
            add_mock):
        msg = msg_factories.ForceSubtaskResultsResponse()
        msg.subtask_results_rejected = None
        library.interpret(msg)
        accepted_mock.assert_called_once_with(
            subtask_id=msg.subtask_id,
            accepted_ts=msg.subtask_results_accepted.payment_ts,
        )
        add_mock.assert_called_once_with(
            msg=msg.subtask_results_accepted,
            node_id=mock.ANY,
            local_role=Actor.Provider,
            remote_role=Actor.Requestor,
        )

    @mock.patch("golem.network.history.add")
    @mock.patch("golem.task.taskserver.TaskServer.subtask_rejected")
    def test_force_subtask_results_response_rejected(
            self,
            rejected_mock,
            add_mock):
        msg = msg_factories.ForceSubtaskResultsResponse()
        msg.subtask_results_accepted = None
        library.interpret(msg)
        rejected_mock.assert_called_once_with(
            subtask_id=msg.subtask_id,
        )
        add_mock.assert_called_once_with(
            msg=msg.subtask_results_rejected,
            node_id=mock.ANY,
            local_role=Actor.Provider,
            remote_role=Actor.Requestor,
        )

    @mock.patch('golem.task.taskmanager.TaskManager.task_computation_failure')
    def test_fgtr_service_refused(self, tcf):
        fgtr = msg_factories.ForceGetTaskResult()
        sr = msg_factories.ServiceRefused(subtask_id=fgtr.subtask_id)
        library.interpret(sr, response_to=fgtr)
        tcf.assert_called_once_with(
            fgtr.subtask_id,
            'Concent refused to assist in forced results download')

    @mock.patch('golem.task.taskmanager.TaskManager.task_computation_failure')
    def test_force_get_task_result_rejected(self, tcf):
        fgtrr = msg_factories.ForceGetTaskResultRejected()
        library.interpret(fgtrr, response_to=fgtrr.force_get_task_result)
        tcf.assert_called_once_with(
            fgtrr.subtask_id,
            'Concent claims ForceGetTaskResult no longer possible'
        )

    @mock.patch('golem.network.concent.received_handler.logger.debug')
    def test_ack_force_get_task_result(self, log):
        afgtr = msg_factories.AckForceGetTaskResult()
        library.interpret(afgtr, response_to=afgtr.force_get_task_result)
        self.assertEqual(log.call_count, 1)

    def test_force_get_task_result_upload(self):

        wtr = taskserver_factories.WaitingTaskResultFactory(
            result_path=self.path)
        rct = msg_factories.ReportComputedTask(subtask_id=wtr.subtask_id)
        fgtru = msg_factories.ForceGetTaskResultUploadFactory(
            force_get_task_result__report_computed_task=rct)

        self.task_server.results_to_send[wtr.subtask_id] = wtr
        library.interpret(fgtru)

        self.cf_transfer.assert_called_once()
        self.assertEqual(self.cf_transfer.call_args[0][0],
                         wtr.result_path)
        self.assertEqual(self.cf_transfer.call_args[0][1],
                         fgtru.file_transfer_token)

    @mock.patch('golem.network.concent.received_handler.logger.warning')
    def test_force_get_task_result_upload_no_ftt(self, log_mock):
        fgtru = msg_factories.ForceGetTaskResultUploadFactory(
            file_transfer_token=None)
        library.interpret(fgtru)
        self.cf_transfer.assert_not_called()
        log_mock.assert_called_once()
        self.assertIn('File Transfer Token invalid', log_mock.call_args[0][0])

    @mock.patch('golem.network.concent.received_handler.logger.warning')
    def test_force_get_task_result_upload_ftt_not_upload(self, log_mock):
        fgtru = msg_factories.ForceGetTaskResultUploadFactory(
            file_transfer_token__download=True)
        library.interpret(fgtru)
        self.cf_transfer.assert_not_called()
        log_mock.assert_called_once()
        self.assertIn('File Transfer Token invalid', log_mock.call_args[0][0])

    @mock.patch('golem.network.concent.received_handler.logger.warning')
    def test_force_get_task_result_upload_wtr_not_found(self, log_mock):
        fgtru = msg_factories.ForceGetTaskResultUploadFactory()
        library.interpret(fgtru)
        self.cf_transfer.assert_not_called()
        log_mock.assert_called_once()
        self.assertIn('Cannot find the subtask', log_mock.call_args[0][0])


# pylint: enable=no-self-use
