# pylint: disable=protected-access
import gc
import unittest
import unittest.mock as mock

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

    @mock.patch("golem.network.concent.helpers.process_report_computed_task")
    def test_concents_force_report_computed_task(self, process_mock):
        msg = msg_factories.ForceReportComputedTask()
        library.interpret(msg)
        process_mock.assert_called_once_with(
            msg=msg.report_computed_task,
            task_session=None,
        )
# pylint: enable=no-self-use
