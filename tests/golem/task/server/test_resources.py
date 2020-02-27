# pylint: disable=protected-access
from unittest import mock

from twisted.internet.defer import Deferred

from golem_messages import cryptography
from golem_messages import utils as msg_utils
from golem_messages.factories.datastructures import p2p as dt_p2p_factory
from golem_messages.factories import helpers as msg_helpers

from golem.network.p2p.local_node import LocalNode
from golem.task.server.resources import TaskResourcesMixin
from golem.task.tasksession import TaskSession
from golem.testutils import TestWithClient


@mock.patch(
    "golem.task.server.resources.TaskResourcesMixin._start_handshake_timer",
)
class TestResourceHandhsake(TestWithClient):
    def setUp(self):
        super().setUp()
        self.server = TaskResourcesMixin()
        self.server.sessions = {}
        self.server.resource_handshakes = {}
        self.server.client = self.client
        self.server.node = LocalNode(**dt_p2p_factory.Node().to_dict())
        self.server.resource_manager.storage.get_dir.return_value = self.tempdir
        self.ecc = cryptography.ECCx(None)
        self.task_id = msg_helpers.fake_golem_uuid(self.public_key)

    @property
    def public_key(self):
        return msg_utils.encode_hex(self.ecc.raw_pubkey)

    @property
    def key_id(self):
        return self.public_key[2:]

    @mock.patch(
        "golem.task.server.resources."
        "TaskResourcesMixin._share_handshake_nonce",
    )
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

    @mock.patch('golem.task.server.resources.msg_queue.put')
    def test_start_handshake_nonce_callback(self, mock_queue, *_):
        deferred = Deferred()
        self.server.resource_manager.add_file.return_value = deferred
        self.server.start_handshake(
            key_id=self.key_id,
            task_id=self.task_id,
        )

        exception = False

        def exception_on_error(error):
            nonlocal exception
            exception = error

        deferred.addErrback(exception_on_error)
        deferred.callback(('result', None))

        if exception:
            raise Exception(exception)

        mock_queue.assert_called_once_with(
            node_id=self.key_id, msg=mock.ANY, timeout=mock.ANY)

    def test_start_handshake_nonce_errback(self, *_):
        deferred = Deferred()
        self.server.resource_manager.add_file.return_value = deferred
        ts = mock.Mock(TaskSession)
        self.server.sessions[self.key_id] = ts
        self.server.start_handshake(
            key_id=self.key_id,
            task_id=self.task_id,
        )

        exception = False

        def exception_on_error(error):
            nonlocal exception
            exception = error

        deferred.addErrback(exception_on_error)
        deferred.errback(('result', None))

        if exception:
            raise Exception(exception)

        ts._handshake_error.assert_called_once_with(self.key_id, mock.ANY)

    @mock.patch(
        "golem.task.server.resources."
        "TaskResourcesMixin._share_handshake_nonce",
    )
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
