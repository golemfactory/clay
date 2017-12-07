import os
import uuid
from unittest import skipIf, TestCase
from unittest.mock import Mock, ANY, patch

from pathlib import Path
from requests import ConnectionError

from golem.network.hyperdrive.client import HyperdriveClient
from golem.resource.dirmanager import DirManager
from golem.resource.hyperdrive.resourcesmanager import \
    HyperdriveResourceManager, HyperdrivePeerManager
from golem.testutils import TempDirFixture
from tests.golem.resource.base.common import AddGetResources


def running():
    try:
        return HyperdriveClient().id()
    except ConnectionError:
        return False


class TestHyperdrivePeerManager(TestCase):

    def test(self):
        own_address = {'TCP': ('1.1.1.1', 3282)}
        peer_address = {'TCP': ('1.2.3.4', 3282)}

        metadata = {'hyperg': peer_address}
        task_id = str(uuid.uuid4())

        node = Mock()
        node.key = str(uuid.uuid4())

        peer_manager = HyperdrivePeerManager(own_address)
        peer_manager.interpret_metadata(metadata, None, None, node)

        assert len(peer_manager._peers) == 1
        assert len(peer_manager._tasks) == 0
        assert len(peer_manager.get_for_task(task_id)) == 1

        peer_manager.interpret_metadata(metadata, None, None, node)

        assert len(peer_manager._peers) == 1
        assert len(peer_manager._tasks) == 0
        assert len(peer_manager.get_for_task(task_id)) == 1

        peer_manager.add(task_id, node.key)

        assert len(peer_manager._peers) == 1
        assert len(peer_manager._tasks) == 1
        assert len(peer_manager.get_for_task(task_id)) == 2

        peer_manager.remove(task_id, node.key)

        assert len(peer_manager._peers) == 0
        assert len(peer_manager._tasks) == 1
        assert len(peer_manager.get_for_task(task_id)) == 1


class TestHyperdriveResourceManager(TempDirFixture):

    def setUp(self):
        super().setUp()

        self.task_id = str(uuid.uuid4())
        self.handle_retries = Mock()
        self.dir_manager = DirManager(self.tempdir)
        self.resource_manager = HyperdriveResourceManager(self.dir_manager)
        self.resource_manager._handle_retries = self.handle_retries

        file_name = 'test_file'
        file_path = os.path.join(self.tempdir, file_name)
        Path(file_path).touch()

        self.files = {file_path: file_name}

    def test_add_files_invalid_paths(self):
        files = {str(uuid.uuid4()): 'does_not_exist'}
        self.resource_manager._add_files(files, self.task_id,
                                         resource_hash=None)
        assert not self.handle_retries.called

    def test_add_files_empty_resource_hash(self):
        self.resource_manager._add_files(self.files, self.task_id,
                                         resource_hash=None)

        self.handle_retries.assert_called_once_with(
            ANY, self.resource_manager.commands.add, ANY,
            client_options=None,
            id=ANY,
            obj_id=ANY,
            raise_exc=True
        )

    def test_add_files_with_resource_hash(self):
        self.resource_manager._add_files(self.files, self.task_id,
                                         resource_hash=str(uuid.uuid4()))

        self.handle_retries.assert_called_once_with(
            ANY, self.resource_manager.commands.restore, ANY,
            client_options=None,
            id=ANY,
            obj_id=ANY,
            raise_exc=True
        )

    @patch('golem.resource.base.resourcesmanager.async_run')
    def test_add_task_failure(self, async_run):

        def mock_async_run(request, _success=None, error=None):
            try:
                request.method(*request.args,
                               **request.kwargs)
            except Exception as exc:
                error(exc)

        self.resource_manager._add_task = Mock(side_effect=Exception)
        self.resource_manager._add_task_error = Mock()
        async_run.side_effect = mock_async_run

        self.resource_manager.add_task(self.files, self.task_id,
                                       resource_hash=str(uuid.uuid4()))

        assert self.resource_manager._add_task_error.called


@skipIf(not running(), "Hyperdrive daemon isn't running")
class TestHyperdriveResources(AddGetResources):
    __test__ = True
    _resource_manager_class = HyperdriveResourceManager
