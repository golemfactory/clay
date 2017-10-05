import os
import uuid

from mock import Mock, patch

from golem.network.transport.message import MessageResourceHandshakeStart, \
    MessageWantToComputeTask
from golem.resource.base.resourcesmanager import ResourceStorage
from golem.resource.dirmanager import DirManager
from golem.resource.resourcehandshake import ResourceHandshake, \
    ResourceHandshakeSessionMixin
from golem.testutils import TempDirFixture


class TestResourceHandshake(TempDirFixture):

    def setUp(self):
        super().setUp()
        key_id = str(uuid.uuid4())
        self.handshake = ResourceHandshake(key_id)

    def test_start(self):
        handshake = self.handshake
        assert not handshake.started()

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

        assert handshake.local_verified is None
        assert not handshake.verify_local('invalid nonce')
        assert handshake.local_verified is False

        assert handshake.verify_local(handshake.nonce)
        assert handshake.local_verified is True
        assert handshake.remote_verified is None
        assert not handshake.success()
        assert not handshake.finished()

        handshake.remote_verdict(False)

        assert handshake.remote_verified is False
        assert not handshake.success()
        assert handshake.finished()

        handshake.remote_verdict(True)

        assert handshake.remote_verified is True
        assert handshake.success()
        assert handshake.finished()


@patch('golem.core.async.async_run')
@patch('twisted.internet.reactor', create=True)
@patch('twisted.internet.task', create=True)
class TestResourceHandshakeSessionMixin(TempDirFixture):

    def setUp(self):
        super().setUp()

        self.message = dict(
            node_name='test node',
            task_id=str(uuid.uuid4()),
            perf_index=4000,
            price=5,
            max_resource_size=10 * 10 ** 8,
            max_memory_size=10 * 10 ** 8,
            num_cores=10
        )

    def test_request_task(self, *_):

        local_session = MockTaskSession(self.tempdir)
        local_session._start_handshake = Mock()
        local_session.send = Mock()

        local_session.request_task(**self.message)
        assert local_session._start_handshake.called

        local_session._start_handshake.reset_mock()
        local_session.send.reset_mock()

        local_session.task_server.deny_set.add(local_session.key_id)
        local_session.request_task(**self.message)
        msg = MessageWantToComputeTask(**self.message)

        assert not local_session._start_handshake.called
        assert local_session.send.called

        call_dict = local_session.send.call_args[0][0].__dict__
        call_dict.pop('timestamp')

        msg_dict = msg.__dict__
        msg_dict.pop('timestamp')

        assert call_dict == msg_dict


class MockTaskSession(ResourceHandshakeSessionMixin):

    def __init__(self, data_dir,
                 successful_downloads=True, successful_uploads=True, **kwargs):

        ResourceHandshakeSessionMixin.__init__(self)

        self.content_to_pull = str(uuid.uuid4())
        self.successful_downloads = successful_downloads
        self.successful_uploads = successful_uploads

        dir_manager = DirManager(data_dir)
        get_dir = dir_manager.get_task_resource_dir

        self.key_id = str(uuid.uuid4())
        self.data_dir = data_dir
        self.task_server = Mock(
            deny_set=set(),
            resource_handshakes=dict(),
            task_manager=Mock(
                task_result_manager=Mock(
                    resource_manager=Mock(
                        storage=ResourceStorage(dir_manager, get_dir),
                        pull_resource=self.__pull_resource
                    )
                )
            )
        )


    @property
    def resource_manager(self):
        return self.task_manager.task_result_manager.resource_manager

    def __pull_resource(self, entry, task_id, success, error, **kwargs):

        resource_path, resource_hash = entry

        if not self.successful_downloads:
            return error(Exception('Test exception'))

        directory = self.resource_manager.storage.get_dir(task_id)
        path = os.path.join(directory, resource_path)

        with open(path, 'w') as f:
            f.write(self.content_to_pull)

        return success(entry)


def mock_async_run(async_request, success, error):
    m, a, k = async_request.method, async_request.args, async_request.kwargs

    try:
        result = m(*a, **k)
    except Exception as exc:
        error(exc)
    else:
        success(result)
