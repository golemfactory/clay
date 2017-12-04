import uuid
from unittest import skipIf, TestCase

import os
from mock import Mock
from requests import ConnectionError

from golem.network.hyperdrive.client import HyperdriveClient
from golem.resource.base.resourcetest import AddGetResources
from golem.resource.dirmanager import DirManager
from golem.resource.hyperdrive.resourcesmanager import \
    HyperdriveResourceManager, HyperdrivePeerManager
from golem.testutils import TempDirFixture


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

    def test_add_files(self):
        dir_manager = DirManager(self.tempdir)
        resource_manager = HyperdriveResourceManager(dir_manager)
        resource_manager._handle_retries = Mock()

        task_id = str(uuid.uuid4())
        resource_hash = None
        files = {str(uuid.uuid4()): 'does_not_exist'}

        # Invalid file paths
        resource_manager._add_files(files, task_id, resource_hash=resource_hash)
        assert not resource_manager._handle_retries.called

        # Create files
        file_name = 'test_file'
        file_path = os.path.join(self.tempdir, file_name)
        files = {file_path: file_name}
        open(file_path, 'w').close()

        # Valid file paths, empty resource hash
        resource_manager._add_files(files, task_id, resource_hash=resource_hash)
        assert resource_manager._handle_retries.called
        command = resource_manager._handle_retries.call_args[0][1]
        assert command == resource_manager.commands.add

        resource_manager._handle_retries.reset_mock()

        # Valid file paths, non-empty resource hash
        resource_hash = str(uuid.uuid4())
        resource_manager._add_files(files, task_id, resource_hash=resource_hash)
        assert resource_manager._handle_retries.called
        command = resource_manager._handle_retries.call_args[0][1]
        assert command == resource_manager.commands.restore


@skipIf(not running(), "Hyperdrive daemon isn't running")
class TestHyperdriveResources(AddGetResources):
    __test__ = True
    _resource_manager_class = HyperdriveResourceManager
