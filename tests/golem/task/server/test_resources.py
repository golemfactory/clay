# pylint: disable=protected-access
from unittest import mock

from golem_messages import cryptography
from golem_messages import utils as msg_utils
from golem_messages.factories import helpers as msg_helpers

from golem.task.taskkeeper import TaskHeaderKeeper
from golem.task.server.resources import TaskResourcesMixin
from golem.testutils import TestWithClient


class TestTaskResourcesMixin(TestWithClient):
    def setUp(self):
        super().setUp()
        self.server = TaskResourcesMixin()
        self.server.task_manager = self.client.task_manager
        self.server.client = self.client
        self.server.task_keeper = TaskHeaderKeeper(
            environments_manager=self.client.environments_manager,
            node=self.client.node,
            min_price=0
        )

    def test_request_resource(self):
        assert self.server.request_resource("task_id1", "subtask_id", [])


@mock.patch(
    "golem.task.server.resources.TaskResourcesMixin._start_handshake_timer",
)
@mock.patch(
    "golem.task.server.resources.TaskResourcesMixin._share_handshake_nonce",
)
class TestResourceHandhsake(TestWithClient):
    def setUp(self):
        super().setUp()
        self.server = TaskResourcesMixin()
        self.server.resource_handshakes = {}
        self.server.client = self.client
        self.server.resource_manager.storage.get_dir.return_value = self.tempdir
        self.ecc = cryptography.ECCx(None)
        self.task_id = msg_helpers.fake_golem_uuid(self.public_key)

    @property
    def public_key(self):
        return msg_utils.encode_hex(self.ecc.raw_pubkey)

    @property
    def key_id(self):
        return self.public_key[2:]

    def test_start_handshake(self, mock_share, mock_timer, *_):
        self.server.start_handshake(
            key_id=self.key_id,
            task_id=self.task_id,
        )
        self.assertIn(
            self.key_id,
            self.server.resource_handshakes,
        )
        mock_timer.assert_called_once_with(self.key_id)
        mock_share.assert_called_once_with(self.key_id)

    @mock.patch(
        "golem.resource.resourcehandshake.ResourceHandshake.start",
        side_effect=RuntimeError("Intentional error"),
    )
    def test_start_handshake_exception(
            self,
            mock_start,
            mock_share,
            mock_timer,
            *_,
    ):
        self.server.start_handshake(
            key_id=self.key_id,
            task_id=self.task_id,
        )
        mock_start.assert_called_once_with(mock.ANY)
        mock_timer.assert_not_called()
        mock_share.assert_not_called()

    @mock.patch(
        "golem.task.server.resources.TaskResourcesMixin.disallow_node",
        create=True,
    )
    def test_timeout_handshake_missing(self, disallow_mock, *_):
        self.server._handshake_timeout(self.key_id)
        disallow_mock.assert_not_called()

    @mock.patch(
        "golem.task.server.resources.TaskResourcesMixin.disallow_node",
        create=True,
    )
    def test_timeout_handshake_success(self, disallow_mock, *_):
        self.server.start_handshake(
            key_id=self.key_id,
            task_id=self.task_id,
        )
        self.server.resource_handshakes[self.key_id].local_result = True
        self.server.resource_handshakes[self.key_id].remote_result = True
        self.server._handshake_timeout(self.key_id)
        disallow_mock.assert_not_called()

    @mock.patch(
        "golem.task.server.resources.TaskResourcesMixin.disallow_node",
        create=True,
    )
    def test_timeout(self, disallow_mock, *_):
        self.server.start_handshake(
            key_id=self.key_id,
            task_id=self.task_id,
        )
        self.server._handshake_timeout(self.key_id)
        disallow_mock.assert_called_once_with(
            node_id=self.key_id,
            timeout_seconds=mock.ANY,
            persist=False,
        )
