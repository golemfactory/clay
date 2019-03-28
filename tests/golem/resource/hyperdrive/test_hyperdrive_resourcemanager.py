import os
import uuid

from pathlib import Path
from unittest import skipIf, TestCase
from unittest.mock import patch, Mock

from requests import ConnectionError
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure

from golem.network.hyperdrive.client import HyperdriveClient
from golem.resource.dirmanager import DirManager
from golem.resource.hyperdrive.resource import Resource, ResourceError
from golem.resource.hyperdrive.resourcesmanager import \
    HyperdriveResourceManager, DummyResourceManager, handle_async, \
    default_argument_value
from golem.testutils import TempDirFixture
from tests.golem.resource.base.common import AddGetResources
from tests.factories.hyperdrive import hyperdrive_client_kwargs


def running():
    try:
        return HyperdriveClient(**hyperdrive_client_kwargs(wrapped=False)).id()
    except ConnectionError:
        return False


def get_resource_paths(storage, target_resources, task_id):
    resource_paths = []
    for resource in target_resources:
        path = storage.get_path(resource, task_id)
        resource_paths.append(path)
    return resource_paths


class ResourceSetUp(TempDirFixture):

    __test__ = False

    def setUp(self):
        super().setUp()
        self.dir_manager = DirManager(self.path)
        self.node_name = str(uuid.uuid4())
        self.task_id = str(uuid.uuid4())

        self.resources_dir = self.dir_manager.get_task_resource_dir(
            self.task_id)
        self.test_file = os.path.join(self.resources_dir, 'file.0')
        self.test_dir = os.path.join(self.resources_dir, 'dir.0')
        self.test_dir_file = os.path.join(self.test_dir, 'file.1')

        self.split_resources = [
            ['file.0'],
            ['dir.0', 'file.1']
        ]
        self.joined_resources = [
            os.path.join(*r) for r in self.split_resources
        ]
        self.target_resources = [
            os.path.join(self.resources_dir, *self.split_resources[0]),
            os.path.join(self.resources_dir, *self.split_resources[1])
        ]

        for path in self.target_resources:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                f.write("test content")


class TestResourceManagerBase(ResourceSetUp):

    __test__ = True

    def setUp(self):
        super().setUp()
        self.resource_manager = DummyResourceManager(
            self.dir_manager, **hyperdrive_client_kwargs())

    def test_copy_files(self):
        old_resource_dir = self.resource_manager.storage.get_root()
        prev_content = os.listdir(old_resource_dir)

        self.dir_manager.node_name = "another" + self.node_name
        self.resource_manager.storage.copy_dir(old_resource_dir)

        assert os.listdir(self.resource_manager.storage.get_root()) == \
            prev_content

    def test_add_file(self):
        self.resource_manager.add_file(self.test_dir_file, self.task_id)
        resources = self.resource_manager.storage.get_resources(self.task_id)
        assert len(resources) == 1

        with self.assertRaises(RuntimeError):
            self.resource_manager.add_files(['/.!&^%'], self.task_id)

        resources = self.resource_manager.storage.get_resources(self.task_id)
        assert len(resources) == 1

    def test_add_files(self):
        self.resource_manager.add_files(self.target_resources, self.task_id)

        storage = self.resource_manager.storage
        resources = storage.get_resources(self.task_id)

        assert resources

        for resource in resources:
            assert all([r in self.target_resources for r in resource.files])
            assert storage.cache.get_by_path(resource.path) is not None
        assert storage.cache.get_by_path(str(uuid.uuid4())) is None

        storage.cache.clear()

        self.resource_manager.add_files([self.test_dir_file], self.task_id)
        assert len(storage.get_resources(self.task_id)) == 1

        with self.assertRaises(RuntimeError):
            self.resource_manager.add_files(['/.!&^%'], self.task_id)

        assert len(storage.get_resources(self.task_id)) == 1

    def test_add_resources(self):
        storage = self.resource_manager.storage

        resource_paths = get_resource_paths(
            self.resource_manager.storage,
            self.target_resources,
            self.task_id
        )

        self.resource_manager.add_resources(resource_paths, self.task_id,
                                            async_=False)
        resources = storage.get_resources(self.task_id)
        assert len(resources) == 1

        assert len(resources[0].files) == len(self.target_resources)
        assert storage.cache.get_prefix(self.task_id)
        assert storage.cache.get_resources(self.task_id)

        new_task = str(uuid.uuid4())
        self.resource_manager.add_resources(resource_paths, new_task,
                                            async_=False)
        assert len(resources) == len(storage.get_resources(new_task))

        self.resource_manager.add_resources(resource_paths, new_task,
                                            async_=False)
        assert len(resources) == len(storage.get_resources(new_task))

    def test_remove_task(self):
        resource_paths = get_resource_paths(
            self.resource_manager.storage,
            self.target_resources,
            self.task_id
        )
        self.resource_manager.add_resources(resource_paths, self.task_id,
                                            async_=False)
        self.resource_manager.remove_resources(self.task_id)

        assert not self.resource_manager.storage.cache.get_prefix(self.task_id)
        assert not self.resource_manager.storage.get_resources(self.task_id)

    def test_to_from_wire(self):
        entries = []

        for resource in self.joined_resources:
            manager = Resource(
                str(uuid.uuid4()),
                res_id="task",
                path=os.path.dirname(resource),
                files=self.joined_resources,
            )
            entries.append(manager)

        resources = self.resource_manager.from_wire(
            self.resource_manager.to_wire(entries)
        )

        assert len(entries) == len(self.target_resources)
        assert all([r[1][0] in self.joined_resources for r in resources])


@patch('golem.network.hyperdrive.client.HyperdriveClient.restore')
@patch('golem.network.hyperdrive.client.HyperdriveClient.add')
class TestHyperdriveResourceManager(TempDirFixture):

    def setUp(self):
        super().setUp()

        self.task_id = str(uuid.uuid4())
        self.handle_retries = Mock()
        self.dir_manager = DirManager(self.tempdir)
        self.resource_manager = HyperdriveResourceManager(  # noqa pylint: disable=unexpected-keyword-arg
            self.dir_manager,
            **hyperdrive_client_kwargs()
        )
        self.resource_manager._handle_retries = self.handle_retries

        file_name = 'test_file'
        file_path = os.path.join(self.tempdir, file_name)
        Path(file_path).touch()

        self.files = {file_path: file_name}

    def test_add_files_invalid_paths(self, add, restore):
        files = {str(uuid.uuid4()): 'does_not_exist'}
        with self.assertRaises(ResourceError):
            self.resource_manager.add_files(files, self.task_id,
                                            resource_hash=None)
        assert not add.called
        assert not restore.called

    def test_add_files_empty_resource_hash(self, add, restore):
        self.resource_manager.add_files(self.files, self.task_id,
                                        resource_hash=None)
        assert not restore.called
        assert add.called

    def test_add_files_with_resource_hash(self, add, restore):
        self.resource_manager.add_files(self.files, self.task_id,
                                        resource_hash=str(uuid.uuid4()))
        assert restore.called
        assert not add.called

    def test_add_resources_failure(self, _add, _restore):
        exc = Exception('Test exception')
        self.resource_manager._add_files = Mock(side_effect=exc)
        deferred = self.resource_manager.add_resources(self.files, self.task_id)
        assert deferred.called
        assert isinstance(deferred.result, Failure)


class TestHandleAsync(TestCase):

    @staticmethod
    def test_async_result():
        success_result = True
        error_result = None
        calls = 0

        from twisted.internet import defer
        defer.setDebugging(True)

        def success(result):
            nonlocal success_result
            success_result = success_result and isinstance(result,
                                                           (str, int, tuple))

        def error(err):
            nonlocal error_result
            error_result = "Error called"
            return err

        @handle_async(error, async_param='_async')
        def func_1(data, _async=True):
            nonlocal calls
            calls += 1
            return data

        func_1("Function 1").addCallback(success)  # pylint: disable=no-member
        assert calls == 1
        assert not error_result
        assert success_result

        func_1("Function 1").addCallbacks(success,  # pylint: disable=no-member
                                          error)
        assert calls == 2
        assert not error_result
        assert success_result

        @handle_async(error, async_param='_async')
        def func_2(data, _async=True):
            nonlocal calls
            calls += 1
            d = Deferred()
            d.callback(data)
            return d

        func_2("Function 2").addCallback(success)
        assert calls == 3
        assert not error_result
        assert success_result

        func_2("Function 2").addCallbacks(success, error)
        assert calls == 4
        assert not error_result
        assert success_result

    @staticmethod
    def test_async_deferred_error():
        success_result = None
        error_result = None
        calls = 0

        def success(result):
            nonlocal success_result
            success_result = "Success called: {}".format(result)

        def error(err):
            nonlocal error_result
            error_result = True
            return err

        @handle_async(error, async_param='_async')
        def func_1(data, _async=True):
            nonlocal calls
            calls += 1
            raise RuntimeError(data)

        @handle_async(error, async_param='_async')
        def func_2(data, _async=True):
            nonlocal calls
            calls += 1
            d = Deferred()
            d.errback(RuntimeError(data))
            return d

        func_1("Function 1").addCallback(success)
        assert calls == 1
        assert error_result
        assert not success_result

        func_1("Function 1").addCallbacks(success, error)
        assert calls == 2
        assert error_result
        assert not success_result

        func_2("Function 2").addCallback(success)
        assert calls == 3
        assert error_result
        assert not success_result

        func_2("Function 2").addCallbacks(success, error)
        assert calls == 4
        assert error_result
        assert not success_result

    @staticmethod
    def test_sync():
        error_result = None

        def error(*_):
            nonlocal error_result
            error_result = "Should not have been called"

        @handle_async(error)
        def func(data):
            return data

        for func_data in [1, "Str", ("tup", "le")]:
            assert func(func_data) == func_data
        assert not error_result

    def test_sync_exception(self):
        error_result = None

        def error(*_):
            nonlocal error_result
            error_result = "Should not have been called"

        @handle_async(error)
        def func(data):
            raise RuntimeError(data)

        for func_data in [1, "Str", ("tup", "le")]:
            with self.assertRaises(RuntimeError):
                func(func_data)
        assert not error_result


class TestDefaultArgumentValue(TestCase):

    @staticmethod
    def test_existing():
        def func(_a=0, _b=None, _c="test"):
            pass

        assert default_argument_value(func, '_a') == 0
        assert default_argument_value(func, '_b') is None
        assert default_argument_value(func, '_c') == 'test'

    @staticmethod
    def test_missing():
        def func(_a, _b=1, _c="test"):
            pass

        assert default_argument_value(func, '_a') is None
        assert default_argument_value(func, '_d') is None


@skipIf(not running(), "Hyperdrive daemon isn't running")
class TestHyperdriveResources(AddGetResources):
    __test__ = True
    _resource_manager_class = HyperdriveResourceManager
