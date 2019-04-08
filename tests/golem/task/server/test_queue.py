# pylint: disable=protected-access
from unittest import mock
import uuid

from golem_messages.factories import tasks as tasks_factories

from golem import testutils
from golem.network import nodeskeeper
from golem.task import taskkeeper
from golem.task.server import queue as srv_queue

class TestTaskResourcesMixin(
        testutils.DatabaseFixture,
        testutils.TestWithClient,
):
    def setUp(self):
        super().setUp()
        self.server = srv_queue.TaskMessagesQueueMixin()
        self.server._add_pending_request = mock.MagicMock()
        self.server.task_manager = self.client.task_manager
        self.server.client = self.client
        self.server.task_keeper = taskkeeper.TaskHeaderKeeper(
            environments_manager=self.client.environments_manager,
            node=self.client.node,
            min_price=0
        )
        self.server.new_session_prepare = mock.MagicMock()
        self.server.remove_pending_conn = mock.MagicMock()
        self.server.remove_responses = mock.MagicMock()
        self.server.response_list = {}
        self.server.pending_connections = {}

        self.message = tasks_factories.ReportComputedTaskFactory()
        self.node_id = self.message.task_to_compute.want_to_compute_task\
            .task_header.task_owner.key
        self.session = mock.MagicMock()
        self.conn_id = str(uuid.uuid4())

    @mock.patch("golem.network.transport.msg_queue.put")
    def test_send_message(self, mock_put, *_):
        nodeskeeper.store(
            self.message.task_to_compute.want_to_compute_task.task_header\
                .task_owner,
        )
        self.server.send_message(
            node_id=self.node_id,
            msg=self.message,
        )
        mock_put.assert_called_once_with(
            self.node_id,
            self.message,
        )

    @mock.patch("golem.network.transport.msg_queue.get")
    def test_conn_established(self, mock_get, *_):
        mock_get.return_value = [self.message, ]
        self.server.msg_queue_connection_established(
            self.session,
            self.conn_id,
            self.node_id,
        )
        self.server.new_session_prepare.assert_called_once_with(
            session=self.session,
            key_id=self.node_id,
            conn_id=self.conn_id,
        )
        self.session.send_hello.assert_called_once_with()
        mock_get.assert_called_once_with(self.node_id)
        self.session.send.assert_called_once_with(self.message)

    @mock.patch(
        "golem.task.server.queue.TaskMessagesQueueMixin"
        ".msg_queue_connection_established",
    )
    def test_conn_failure(self, mock_established, *_):
        self.server.msg_queue_connection_failure(
            self.conn_id,
            node_id=self.node_id,
        )
        self.server.response_list[self.conn_id][0](self.session)
        mock_established.assert_called_once_with(
            self.session,
            self.conn_id,
            node_id=self.node_id,
        )

    def test_conn_final_failure(self, *_):
        self.server.msg_queue_connection_final_failure(
            self.conn_id,
            node_id=self.node_id,
        )
