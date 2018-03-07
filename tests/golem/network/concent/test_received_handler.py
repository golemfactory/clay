# pylint: disable=protected-access
import gc
import unittest
import unittest.mock as mock

from golem_messages import exceptions as msg_exceptions
from golem_messages import message

from golem import testutils
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


# pylint: disable=no-self-use
class TaskServerMessageHandlerTestCase(
        testutils.DatabaseFixture, testutils.TestWithClient):
    def setUp(self):
        for parent in self.__class__.__bases__:
            parent.setUp(self)
        self.task_server = taskserver_factories.TaskServer(
            client=self.client,
        )
        # received_handler.TaskServerMessageHandler is instantiated
        # in TaskServer.__init__

    def tearDown(self):
        # Remove registered handlers
        del self.task_server
        gc.collect()

    @mock.patch("golem.task.taskserver.TaskServer.concent_refused")
    def test_concent_service_refused(self, refused_mock):
        msg = msg_factories.ServiceRefused()
        library.interpret(msg)
        refused_mock.assert_called_once_with(
            subtask_id=msg.subtask_id,
            reason=msg.reason,
        )

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

# pylint: enable=no-self-use
