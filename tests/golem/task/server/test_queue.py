# pylint: disable=protected-access
from unittest import mock
import uuid

from freezegun import freeze_time
from golem_messages.factories import tasks as tasks_factories

from golem import testutils
from golem.network.transport import tcpserver
from golem.task import taskkeeper
from golem.task.server import queue_ as srv_queue

class TestTaskQueueMixin(
        testutils.DatabaseFixture,
        testutils.TestWithClient,
):
    def setUp(self):
        super().setUp()
        self.server = srv_queue.TaskMessagesQueueMixin()
        self.server._add_pending_request = mock.MagicMock()
        self.server._mark_connected = mock.MagicMock()
        self.server.task_manager = self.client.task_manager
        self.server.client = self.client
        self.server.task_keeper = taskkeeper.TaskHeaderKeeper(
            environments_manager=self.client.environments_manager,
            node=self.client.node,
            min_price=0
        )
        self.server.remove_pending_conn = mock.MagicMock()
        self.server.pending_connections = {}
        self.server.forwarded_session_requests = {}

        self.message = tasks_factories.ReportComputedTaskFactory()
        self.node_id = self.message.task_to_compute.want_to_compute_task\
            .task_header.task_owner.key
        self.session = mock.MagicMock()
        self.conn_id = str(uuid.uuid4())

    def test_conn_established(self, *_):
        self.server.msg_queue_connection_established(
            self.session,
            self.conn_id,
            self.node_id,
        )
        self.assertEqual(self.node_id, self.session.key_id)
        self.assertEqual(self.conn_id, self.session.conn_id)
        self.session.send_hello.assert_called_once_with()

    @freeze_time('2019-04-15 11:15:00')
    def test_conn_failure(self, *_):
        pc = self.server.pending_connections[self.conn_id] = mock.MagicMock()
        self.server.msg_queue_connection_failure(
            self.conn_id,
            node_id=self.node_id,
        )
        self.assertEqual(pc.status, tcpserver.PenConnStatus.WaitingAlt)
        self.assertEqual(pc.time, 1555326900.0)

    def test_conn_final_failure(self, *_):
        self.server.msg_queue_connection_final_failure(
            self.conn_id,
            node_id=self.node_id,
        )
