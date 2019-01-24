# pylint: disable=protected-access
import os
import types
import uuid

from pathlib import Path
from unittest.mock import Mock, patch, ANY

from golem_messages import message
from golem_messages.factories.datastructures import tasks as dt_tasks_factory
from twisted.internet.defer import Deferred

from golem.network.hyperdrive.client import HyperdriveClientOptions, \
    HyperdriveClient, to_hyperg_peer
from golem.resource.dirmanager import DirManager
from golem.resource.hyperdrive.resource import ResourceStorage
from golem.resource.hyperdrive.resourcesmanager import HyperdriveResourceManager
from golem.resource.resourcehandshake import ResourceHandshake, \
    ResourceHandshakeSessionMixin
from golem.task.acl import get_acl
from golem.testutils import TempDirFixture, DatabaseFixture


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

    def test_request_task_handshake(self, *_):
        self.session.send = Mock()

        self.session.request_task(**self.message)
        self.session._start_handshake.assert_called_once()

    def test_request_task_success(self, *_):
        self.session._handshake_required = Mock()
        self.session.send = Mock()
        wtct_dict = {k: v for k, v in self.message.items()}
        wtct_dict.pop('task_id')
        wtct_dict.update({
            'task_header': self.task_header.to_dict()
        })

        self.session._handshake_required.return_value = False
        self.session.request_task(**self.message)

        self.session.disconnect.assert_not_called()
        self.session.send.assert_called()

        sent_wtct = self.session.send.call_args[0][0]

        msg = message.tasks.WantToComputeTask(**wtct_dict)
        self.assertEqual(sent_wtct, msg)

    def test_request_task_failure(self, *_):
        self.session._handshake_required = Mock()
        self.session._handshake_error = Mock()

        self.session._handshake_required.return_value = False
        self.session._block_peer(self.session.key_id)
        self.session.request_task(**self.message)

        assert not self.session._start_handshake.called
        assert self.session._handshake_error.called

    @patch(
        "golem.resource.resourcehandshake.ResourceHandshakeSessionMixin"
        "._handshake_required",
        return_value=False,
    )
    @patch(
        "golem.resource.resourcehandshake.ResourceHandshakeSessionMixin"
        "._handshake_error",
    )
    def test_request_task_concent_required(self, hs_error_mock, *_):
        self.session.task_server.client.concent_service.enabled = True
        self.session.task_server.task_keeper \
            .task_headers[self.message['task_id']].concent_enabled = False

        self.session.request_task(**self.message)
        self.session.send.assert_not_called()
        hs_error_mock.assert_called_once_with(
            self.session.key_id,
            "Concent required",
        )

    @patch(
        "golem.resource.resourcehandshake.ResourceHandshakeSessionMixin"
        "._handshake_required",
        return_value=False,
    )
    def test_request_task_concent_enabled(self, *_):
        self.session.task_server.client.concent_service.enabled = True
        self.session.task_server.task_keeper \
            .task_headers[self.message['task_id']].concent_enabled = True

        self.session.request_task(**self.message)
        self.session.send.assert_called_once()
        msg: message.tasks.WantToComputeTask = self.session.send.call_args[0][0]
        self.assertIsInstance(msg, message.tasks.WantToComputeTask)
        self.assertTrue(msg.concent_enabled)

    @patch(
        "golem.resource.resourcehandshake.ResourceHandshakeSessionMixin"
        "._handshake_required",
        return_value=False,
    )
    def test_request_task_concent_disabled(self, *_):
        self.session.task_server.client.concent_service.enabled = False

        self.session.request_task(**self.message)
        self.session.send.assert_called_once()
        msg: message.tasks.WantToComputeTask = self.session.send.call_args[0][0]
        self.assertIsInstance(msg, message.tasks.WantToComputeTask)
        self.assertFalse(msg.concent_enabled)

    def test_react_to_resource_handshake_start(self, *_):
        self.session._download_handshake_nonce = Mock()
        self.session._handshake_error = Mock()

        resource = str(uuid.uuid4())
        msg = message.resources.ResourceHandshakeStart(resource=resource)
        self.session._react_to_resource_handshake_start(msg)

        assert self.session._start_handshake.called
        assert not self.session._handshake_error.called
        self.session._download_handshake_nonce.assert_called_with(
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

        assert not self.session._download_handshake_nonce.called
        assert not self.session._start_handshake.called
        assert self.session._handshake_error.called

    def test_react_to_resource_handshake_start_upload_failure(self, *_):
        self.session = MockTaskSession(self.tempdir, successful_uploads=False)
        self.session._download_handshake_nonce = Mock()
        self.session._handshake_error = Mock()

        msg = message.resources.ResourceHandshakeStart(
            resource=str(uuid.uuid4()))

        self.session._react_to_resource_handshake_start(msg)

        assert self.session._handshake_error.called
        assert self.session._download_handshake_nonce.called

    def test_react_to_resource_handshake_start_download_failure(self, *_):
        self.session = MockTaskSession(self.tempdir, successful_downloads=False)
        self.session._start_handshake = Mock()
        self.session._handshake_error = Mock()

        msg = message.resources.ResourceHandshakeStart(
            resource=str(uuid.uuid4()))
        handshake = ResourceHandshake()

        self.session._set_handshake(self.session.key_id, handshake)
        self.session._react_to_resource_handshake_start(msg)

        assert self.session._handshake_error.called

    def test_react_to_resource_handshake_nonce(self, *_):
        self.session._finalize_handshake = Mock()
        self.session._handshake_error = Mock()

        handshake = ResourceHandshake()
        handshake.start(self.tempdir)

        msg = message.resources.ResourceHandshakeNonce(nonce=handshake.nonce)

        self.session._set_handshake(self.session.key_id, handshake)
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

        self.session._set_handshake(self.session.key_id, handshake)
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

        self.session._set_handshake(self.session.key_id, handshake)
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

        self.session._set_handshake(self.session.key_id, handshake)
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
        self.session._set_handshake(self.session.key_id, handshake)

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
        self.session._set_handshake(self.session.key_id, handshake)

        assert self.session._handshake_in_progress(self.session.key_id)

        handshake.local_result = True
        handshake.remote_result = False

        assert not self.session._handshake_in_progress(self.session.key_id)

    def test_start_handshake(self, *_):
        self.session = MockTaskSession(self.tempdir)
        self.session._set_handshake = Mock()
        self.session._start_handshake_timer = Mock()
        self.session._share_handshake_nonce = Mock()

        with patch('golem.resource.resourcehandshake.ResourceHandshake.start',
                   side_effect=RuntimeError('Test exception')):

            self.session._start_handshake(self.session.key_id)

            assert not self.session._set_handshake.called
            assert not self.session._start_handshake_timer.called
            assert not self.session._share_handshake_nonce.called

        self.session._start_handshake(self.session.key_id)

        self.session._set_handshake.assert_called_once()
        assert self.session._start_handshake_timer.called
        assert self.session._share_handshake_nonce.called

    def test_handshake_timer(self, task, *_):
        self.session._start_handshake_timer()
        assert task.deferLater.called

    def test_finalize_handshake(self, *_):
        self.session._finalize_handshake(self.session.key_id)
        task_request_message = {k: v for k, v in self.message.items()}
        task_request_message.pop('task_id')
        task_request_message['task_header'] = self.task_header
        self.session._task_request_message = task_request_message
        assert not self.session.send.called

        handshake = ResourceHandshake()
        handshake.local_result = False
        handshake.remote_result = True
        self.session._set_handshake(self.session.key_id, handshake)

        self.session._finalize_handshake(self.session.key_id)
        assert not self.session.send.called

        self.session._finalize_handshake(self.session.key_id)
        assert not self.session.send.called

        handshake.local_result = True
        handshake.remote_result = True

        self.session._finalize_handshake(self.session.key_id)
        assert self.session.send.called

    def test_handshake_error(self, *_):
        self.session._block_peer = Mock()
        self.session._finalize_handshake = Mock()

        self.session._handshake_error(self.session.key_id, 'Test error')
        assert self.session._block_peer.called
        assert self.session._finalize_handshake.called
        assert self.session.task_server.task_computer.session_closed.called
        assert not self.session.disconnect.called

    def test_handshake_timeout(self, *_):
        self.session._block_peer = Mock()
        self.session._finalize_handshake = Mock()

        self.session._handshake_timeout(self.session.key_id)
        assert not self.session._block_peer.called
        assert not self.session._finalize_handshake.called
        assert not self.session.task_server.task_computer.session_closed.called
        assert not self.session.dropped.called

        handshake = ResourceHandshake()
        handshake.local_result = False
        handshake.remote_result = True
        self.session._set_handshake(self.session.key_id, handshake)

        self.session._handshake_timeout(self.session.key_id)
        assert self.session._block_peer.called
        assert self.session._finalize_handshake.called
        assert self.session.task_server.task_computer.session_closed.called
        assert self.session.dropped.called

    def test_get_set_remove_handshake(self, *_):
        handshake = ResourceHandshake()
        key_id = self.session.key_id

        assert not self.session._get_handshake(key_id)
        self.session._set_handshake(key_id, handshake)
        assert self.session._get_handshake(key_id)
        self.session._remove_handshake(key_id)
        assert not self.session._get_handshake(key_id)

    def test_block_peer(self, *_):
        key_id = self.session.key_id

        assert not self.session._is_peer_blocked(key_id)
        self.session._block_peer(key_id)
        assert self.session._is_peer_blocked(key_id)


@patch('twisted.internet.reactor', create=True)
@patch('twisted.internet.task', create=True)
class TestResourceHandshakeShare(DatabaseFixture):

    def setUp(self):
        super().setUp()
        self.key_id = str(uuid.uuid4())

    def test_flow(self, *_):
        local_dir = os.path.join(self.tempdir, 'local')
        remote_dir = os.path.join(self.tempdir, 'remote')

        os.makedirs(local_dir, exist_ok=True)
        os.makedirs(remote_dir, exist_ok=True)

        local_session = MockTaskSession(local_dir)
        remote_session = MockTaskSession(remote_dir)

        local_session._handshake_error = Mock(
            side_effect=local_session._handshake_error)
        local_session._finalize_handshake = Mock()
        remote_session._handshake_error = Mock(
            side_effect=remote_session._handshake_error)
        remote_session._finalize_handshake = Mock()

        self.__create_task_server(local_session)
        self.__create_task_server(remote_session)

        local_session.key_id = remote_session.task_server.node.key
        remote_session.key_id = local_session.task_server.node.key

        # Start handshake

        local_session._start_handshake(local_session.key_id)
        msg = local_session.send.call_args[0][0]  # noqa pylint: disable=unsubscriptable-object
        local_hash = msg.resource

        remote_session._start_handshake(remote_session.key_id)
        msg = remote_session.send.call_args[0][0]  # noqa pylint: disable=unsubscriptable-object
        remote_hash = msg.resource
        options = Mock()

        local_session.send.reset_mock()
        remote_session.send.reset_mock()

        # Download nonces on both sides
        local_session._download_handshake_nonce(local_session.key_id,
                                                remote_hash, options)
        assert not local_session._handshake_error.called
        assert local_session.send.called

        remote_session._download_handshake_nonce(remote_session.key_id,
                                                 local_hash, options)
        assert not remote_session._handshake_error.called
        assert remote_session.send.called

        # Check self-issued nonce only. Asserts make sure that nonces
        # were verified successfully.

        msg_from_local = local_session.send.call_args[0][0]  # noqa pylint: disable=unsubscriptable-object
        msg_from_remote = remote_session.send.call_args[0][0]  # noqa pylint: disable=unsubscriptable-object

        local_nonce = msg_from_local.nonce
        remote_nonce = msg_from_remote.nonce

        local_session._react_to_resource_handshake_nonce(msg_from_remote)
        remote_session._react_to_resource_handshake_nonce(msg_from_local)

        local_session._react_to_resource_handshake_verdict(
            message.resources.ResourceHandshakeVerdict(
                nonce=remote_nonce, accepted=True)
        )

        remote_session._react_to_resource_handshake_verdict(
            message.resources.ResourceHandshakeVerdict(
                nonce=local_nonce, accepted=True)
        )

        assert local_session._finalize_handshake.called
        assert remote_session._finalize_handshake.called

        assert not local_session._handshake_error.called
        assert not remote_session._handshake_error.called

        assert not local_session.disconnect.called
        assert not remote_session.disconnect.called

    def test_share_handshake_nonce(self, *_):
        session = MockTaskSession(self.tempdir)
        self.__create_task_server(session)

        handshake = ResourceHandshake()
        handshake.start(self.tempdir)

        session._set_handshake(session.key_id, handshake)
        session._share_handshake_nonce(session.key_id)

        assert session.send.called
        msg = session.send.call_args[0][0]  # noqa pylint: disable=unsubscriptable-object
        assert isinstance(msg, message.resources.ResourceHandshakeStart)

    def test_share_handshake_nonce_after_failure(self, *_):
        session = MockTaskSession(self.tempdir)
        self.__create_task_server(session)

        handshake = ResourceHandshake()
        handshake.start(self.tempdir)

        nonce_shared = session._nonce_shared

        def intercept_nonce_shared(*args, **kwargs):
            session._set_handshake(session.key_id, None)
            nonce_shared(*args, **kwargs)

        session._nonce_shared = intercept_nonce_shared

        session._set_handshake(session.key_id, handshake)
        session._share_handshake_nonce(session.key_id)
        assert not session.send.called

    @staticmethod
    def __create_task_server(session):
        from golem.clientconfigdescriptor import ClientConfigDescriptor
        from golem.task.taskserver import TaskServer

        client = Mock(datadir=session.data_dir)
        dir_manager = DirManager(session.data_dir)

        resource_manager = HyperdriveResourceManager(dir_manager=dir_manager)
        resource_manager.successful_uploads = True
        resource_manager.successful_downloads = True

        resource_manager.add_file_org = resource_manager.add_file
        resource_manager.add_file = types.MethodType(_add_file,
                                                     resource_manager)
        resource_manager.pull_resource_org = resource_manager.pull_resource
        resource_manager.pull_resource = types.MethodType(_pull_resource,
                                                          resource_manager)

        with patch("golem.network.concent.handlers_library"
                   ".HandlersLibrary"
                   ".register_handler"):
            task_server = TaskServer(
                node=Mock(client=client, key=str(uuid.uuid4())),
                config_desc=ClientConfigDescriptor(),
                client=client,
                use_docker_manager=False
            )
        task_server.task_manager = Mock(
            task_result_manager=Mock(
                resource_manager=resource_manager
            )
        )

        peers = to_hyperg_peer('127.0.0.1', 3282)
        client_options = HyperdriveClientOptions(
            HyperdriveClient.CLIENT_ID,
            HyperdriveClient.VERSION,
            options=dict(
                peers=peers,
                filtered=peers
            )
        )

        task_server.get_share_options = Mock(return_value=client_options)
        task_server.get_download_options = Mock(return_value=client_options)

        session.task_server = task_server


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
