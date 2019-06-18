# pylint: disable=protected-access
import os
import types
import uuid

from pathlib import Path
from unittest.mock import Mock, patch, ANY

from golem_messages import message
from golem_messages.factories.datastructures import tasks as dt_tasks_factory
from twisted.internet.defer import Deferred

from golem.appconfig import (
    DEFAULT_HYPERDRIVE_RPC_PORT, DEFAULT_HYPERDRIVE_RPC_ADDRESS
)
from golem.network.hyperdrive.daemon_manager import HyperdriveDaemonManager
from golem.resource.dirmanager import DirManager
from golem.resource.hyperdrive.resource import ResourceStorage
from golem.resource.hyperdrive.resourcesmanager import HyperdriveResourceManager
from golem.resource.resourcehandshake import ResourceHandshake, \
    ResourceHandshakeSessionMixin
from golem.task.acl import get_acl
from golem.testutils import TempDirFixture


class TestResourceHandshake(TempDirFixture):

    def setUp(self):
        super().setUp()
        self.handshake = ResourceHandshake()

    def test_start(self):
        handshake = self.handshake
        assert not handshake.started

        handshake.start(self.tempdir)
        assert os.path.exists(handshake.file)
        assert handshake.nonce == handshake.read_nonce(handshake.file)

    def test_status(self):
        handshake = self.handshake

        assert not handshake.success()
        assert not handshake.finished()

        handshake.start(self.tempdir)

        assert not handshake.success()
        assert not handshake.finished()

        assert handshake.local_result is None
        assert not handshake.verify_local('invalid nonce')
        assert handshake.local_result is False

        assert handshake.verify_local(handshake.nonce)
        assert handshake.local_result is True
        assert handshake.remote_result is None
        assert not handshake.success()
        assert not handshake.finished()

        handshake.remote_verdict(False)

        assert handshake.remote_result is False
        assert not handshake.success()
        assert handshake.finished()

        handshake.remote_verdict(True)

        assert handshake.remote_result is True
        assert handshake.success()
        assert handshake.finished()


@patch('twisted.internet.reactor', create=True)
@patch('twisted.internet.task', create=True)
class TestResourceHandshakeSessionMixin(TempDirFixture):

    def setUp(self):
        super().setUp()

        self.key_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())
        self.task_header = dt_tasks_factory.TaskHeaderFactory()
        self.message = dict(
            node_name='test node',
            task_id=task_id,
            perf_index=4000,
            price=5,
            max_resource_size=10 * 10 ** 8,
            max_memory_size=10 * 10 ** 8,
        )
        self.session = MockTaskSession(self.tempdir)
        self.session._start_handshake = Mock()
        self.session.task_server.task_keeper.task_headers = task_headers = {}
        task_headers[task_id] = self.task_header
        self.session.task_server.client.concent_service.enabled = False

    def _set_handshake(self, key_id, handshake):
        self.session.task_server.resource_handshakes[key_id] = handshake

    def test_react_to_resource_handshake_start(self, *_):
        self.session._download_handshake_nonce = Mock()
        self.session._handshake_error = Mock()

        resource = str(uuid.uuid4())
        msg = message.resources.ResourceHandshakeStart(resource=resource)
        self.session._react_to_resource_handshake_start(msg)

        self.session.task_server.start_handshake.assert_called_once_with(
            self.session.key_id,
        )
        self.session._handshake_error.assert_not_called()
        self.session._download_handshake_nonce.assert_called_once_with(
            ANY,
            resource,
            ANY,
        )

    def test_react_to_resource_handshake_start_blocked_peer(self, *_):
        self.session._download_handshake_nonce = Mock()
        self.session._handshake_error = Mock()

        msg = message.resources.ResourceHandshakeStart(
            resource=str(uuid.uuid4()))
        self.session._block_peer(self.session.key_id)
        self.session._react_to_resource_handshake_start(msg)

        self.session._download_handshake_nonce.assert_not_called()
        self.session._handshake_error.assert_called_once_with(
            self.session.key_id,
            'Peer blocked',
        )

    def test_react_to_resource_handshake_nonce(self, *_):
        self.session._finalize_handshake = Mock()
        self.session._handshake_error = Mock()

        handshake = ResourceHandshake()
        handshake.start(self.tempdir)

        msg = message.resources.ResourceHandshakeNonce(nonce=handshake.nonce)

        self._set_handshake(self.session.key_id, handshake)
        self.session._react_to_resource_handshake_nonce(msg)

        assert self.session._finalize_handshake.called
        assert not self.session._handshake_error.called

    def test_react_to_resource_handshake_nonce_failure(self, *_):
        self.session._finalize_handshake = Mock()
        self.session._handshake_error = Mock()

        handshake = ResourceHandshake()
        handshake.start(self.tempdir)

        msg = message.resources.ResourceHandshakeNonce(nonce=handshake.nonce)
        self.session._react_to_resource_handshake_nonce(msg)

        assert not self.session._finalize_handshake.called
        assert self.session._handshake_error.called

        self._set_handshake(self.session.key_id, handshake)
        msg = message.resources.ResourceHandshakeNonce(nonce=str(uuid.uuid4()))
        self.session._react_to_resource_handshake_nonce(msg)

        assert not self.session._finalize_handshake.called
        assert self.session._handshake_error.called

    def test_react_to_resource_handshake_verdict(self, *_):
        self.session._finalize_handshake = Mock()
        self.session._handshake_error = Mock()

        handshake = ResourceHandshake()
        handshake.start(self.tempdir)

        msg = message.resources.ResourceHandshakeVerdict(
            nonce=handshake.nonce,
            accepted=True,
        )
        self.session._react_to_resource_handshake_nonce(msg)

        assert not self.session._finalize_handshake.called
        assert self.session._handshake_error.called

        self._set_handshake(self.session.key_id, handshake)
        msg = message.resources.ResourceHandshakeVerdict(
            nonce=str(uuid.uuid4()),
            accepted=False,
        )
        self.session._react_to_resource_handshake_nonce(msg)

        assert not self.session._finalize_handshake.called
        assert self.session._handshake_error.called

    def test_react_to_resource_handshake_verdict_failure(self, *_):
        self.session = MockTaskSession(self.tempdir, successful_uploads=False)
        self.session._finalize_handshake = Mock()
        self.session._handshake_error = Mock()

        handshake = ResourceHandshake()
        handshake.start(self.tempdir)

        msg = message.resources.ResourceHandshakeVerdict(
            nonce=handshake.nonce,
            accepted=False,
        )
        self.session._react_to_resource_handshake_nonce(msg)

        assert not self.session._finalize_handshake.called
        assert self.session._handshake_error.called

        self._set_handshake(self.session.key_id, handshake)
        msg = message.resources.ResourceHandshakeVerdict(
            nonce=str(uuid.uuid4()),
            accepted=False,
        )
        self.session._react_to_resource_handshake_nonce(msg)

        assert not self.session._finalize_handshake.called
        assert self.session._handshake_error.called

    def test_handshake_required(self, *_):
        self.session._handshake_error = Mock()

        assert not self.session._handshake_required(None)
        assert self.session._handshake_error.called

        self.session._handshake_error.reset_mock()

        assert self.session._handshake_required(self.session.key_id)
        assert not self.session._handshake_in_progress(self.session.key_id)
        assert not self.session._handshake_error.called

        handshake = ResourceHandshake()
        self._set_handshake(self.session.key_id, handshake)

        assert not self.session._handshake_required(self.session.key_id)
        assert self.session._handshake_in_progress(self.session.key_id)
        assert not self.session._handshake_error.called

        handshake.local_result = True
        handshake.remote_result = True

        assert not self.session._handshake_required(self.session.key_id)
        assert not self.session._handshake_in_progress(self.session.key_id)
        assert not self.session._handshake_error.called

        self.session._remove_handshake(self.session.key_id)
        self.session._block_peer(self.session.key_id)

        assert not self.session._handshake_required(self.session.key_id)
        assert not self.session._handshake_in_progress(self.session.key_id)
        assert not self.session._handshake_error.called

    def test_handshake_in_progress(self, *_):
        self.session = MockTaskSession(self.tempdir)
        self.session._handshake_error = Mock()

        assert not self.session._handshake_in_progress(None)
        assert self.session._handshake_error.called

        self.session._handshake_error.reset_mock()

        assert not self.session._handshake_in_progress(self.session.key_id)
        assert not self.session._handshake_error.called

        handshake = ResourceHandshake()
        handshake.start(self.tempdir)
        self._set_handshake(self.session.key_id, handshake)

        assert self.session._handshake_in_progress(self.session.key_id)

        handshake.local_result = True
        handshake.remote_result = False

        assert not self.session._handshake_in_progress(self.session.key_id)

    def test_finalize_handshake(self, *_):
        self.session._finalize_handshake(self.session.key_id)
        self.session.task_server.request_task_by_id.assert_not_called()

        handshake = ResourceHandshake()
        handshake.local_result = False
        handshake.remote_result = True
        handshake.task_id = self.message['task_id']
        self._set_handshake(self.session.key_id, handshake)

        self.session._finalize_handshake(self.session.key_id)
        self.session.task_server.request_task_by_id.assert_not_called()

        self.session._finalize_handshake(self.session.key_id)
        self.session.task_server.request_task_by_id.assert_not_called()

        handshake.local_result = True
        handshake.remote_result = True

        self.session._finalize_handshake(self.session.key_id)
        self.session.task_server.request_task_by_id.assert_called_once_with(
            task_id=handshake.task_id,
        )

    def test_handshake_error(self, *_):
        self.session._block_peer = Mock()
        self.session._finalize_handshake = Mock()

        self.session._handshake_error(self.session.key_id, 'Test error')
        assert self.session._block_peer.called
        assert self.session._finalize_handshake.called
        assert not self.session.disconnect.called

    def test_get_set_remove_handshake(self, *_):
        handshake = ResourceHandshake()
        key_id = self.session.key_id

        assert not self.session._get_handshake(key_id)
        self._set_handshake(key_id, handshake)
        assert self.session._get_handshake(key_id)
        self.session._remove_handshake(key_id)
        assert not self.session._get_handshake(key_id)

    def test_block_peer(self, *_):
        key_id = self.session.key_id

        assert not self.session._is_peer_blocked(key_id)
        self.session._block_peer(key_id)
        assert self.session._is_peer_blocked(key_id)


class MockTaskSession(ResourceHandshakeSessionMixin):

    def __init__(self, data_dir,
                 successful_downloads=True, successful_uploads=True, **_kwargs):

        ResourceHandshakeSessionMixin.__init__(self)

        self.send = Mock()
        self.disconnect = Mock()
        self.dropped = Mock()

        self.content_to_pull = str(uuid.uuid4())
        self.successful_downloads = successful_downloads
        self.successful_uploads = successful_uploads

        self.address = "192.168.0.11"
        self.key_id = str(uuid.uuid4())
        self.address = '1.2.3.4'
        self.data_dir = data_dir

        dir_manager = DirManager(data_dir)
        storage = ResourceStorage(dir_manager,
                                  dir_manager.get_task_resource_dir)
        resource_manager = Mock(
            storage=storage,
            content_to_pull=str(uuid.uuid4()).replace('-', ''),
            successful_uploads=successful_uploads,
            successful_downloads=successful_downloads,
        )
        resource_manager.add_file = types.MethodType(_add_file,
                                                     resource_manager)
        resource_manager.add_file_org = types.MethodType(
            HyperdriveResourceManager.add_file,
            resource_manager
        )
        resource_manager.pull_resource = types.MethodType(_pull_resource,
                                                          resource_manager)
        resource_manager.pull_resource_org = types.MethodType(
            HyperdriveResourceManager.pull_resource,
            resource_manager
        )

        self.task_server = Mock(
            client=Mock(datadir=data_dir),
            node=Mock(key=str(uuid.uuid4())),
            acl=get_acl(Path(data_dir)),
            resource_handshakes=dict(),
            get_key_id=lambda: None,
            task_manager=Mock(
                task_result_manager=Mock(
                    resource_manager=resource_manager
                )
            )
        )


def _pull_resource(self, entry, task_id, success, error, **kwargs):
    if not self.successful_downloads:
        return error(RuntimeError('Test exception'))

    kwargs['async_'] = False
    return self.pull_resource_org(entry, task_id, success, error, **kwargs)


def _add_file(self, path, task_id, **kwargs):
    deferred = Deferred()
    kwargs['async_'] = False

    if self.successful_uploads:
        result = self.add_file_org(path, task_id, **kwargs)
        deferred.callback(result)
    else:
        deferred.errback(RuntimeError('Test exception'))

    return deferred
