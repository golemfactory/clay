import os
import uuid
from pathlib import Path

from golem.resource.hyperdrive.resource import ResourceCache, Resource, \
    ResourceStorage
from golem.testutils import TempDirFixture
from tests.golem.resource.hyperdrive.test_hyperdrive_resourcemanager import \
    ResourceSetUp


class TestResourceCache(TempDirFixture):

    def setUp(self):
        super().setUp()

        self.cache = ResourceCache()
        self.resource_path = str(os.path.join(self.tempdir, 'prefix', 'path'))
        self.resource_name = '\0!abstract_name\0!'
        self.resource_files = [self.resource_name]
        self.resource_hash = str(uuid.uuid4())
        self.prefix = str(os.path.join('abstract', 'prefix'))
        self.task_id = '\0!abstract\0!'

    def test_prefix(self):
        self.cache.set_prefix(self.task_id, self.prefix)
        resource = Resource(
            self.resource_hash,
            task_id=self.task_id,
            files=self.resource_files,
            path=self.resource_path
        )

        assert self.cache.get_prefix(resource.task_id) == self.prefix
        assert self.cache.get_prefix(str(uuid.uuid4())) == ''
        assert self.cache.get_prefix(str(uuid.uuid4()), 'default_value') == \
            'default_value'

        self.cache.add_resource(resource)
        self.cache.remove(resource.task_id)
        assert self.cache.get_prefix(resource.task_id) == ''

    def test_resources(self):
        resource = Resource(
            self.resource_hash,
            task_id=self.task_id,
            files=self.resource_files,
            path=self.resource_path
        )

        new_task_file = 'new_name'
        new_resource = Resource(
            str(uuid.uuid4()),
            task_id=str(uuid.uuid4()),
            files=[new_task_file],
            path=self.resource_path
        )

        def create_file(name):
            directory = os.path.join(self.tempdir, self.resource_path, name)
            os.makedirs(directory, exist_ok=True)
            Path(os.path.join(directory, name)).touch()

        self.cache.add_resource(resource)

        assert self.cache.get_resources(self.task_id) == [resource]
        assert self.cache.get_resources(new_resource.task_id) == []
        assert self.cache.get_resources('unknown') == []
        assert self.cache.has_resource(resource)
        assert not self.cache.has_resource(new_resource)

        assert not new_resource.exists
        create_file(new_task_file)
        self.cache.add_resource(new_resource)
        print(new_resource.path, new_resource.files)
        assert new_resource.exists

        assert self.cache.get_resources(self.task_id) == [resource]
        assert self.cache.get_resources(new_resource.task_id) == [new_resource]
        assert self.cache.get_resources('unknown') == []
        assert self.cache.has_resource(resource)
        assert self.cache.has_resource(new_resource)

        assert self.cache.remove(self.task_id)
        assert self.cache.remove('unknown') == []
        assert self.cache.get_resources(new_resource.task_id) == [new_resource]

    def test_remove(self):
        self._add_all()
        self.cache.remove(self.task_id)
        assert self._all_default_empty()

        new_path = '/other/path'
        new_resource = Resource(
            str(uuid.uuid4()),
            task_id=str(uuid.uuid4()),
            path=new_path,
            files=[new_path]
        )

        self._add_all()
        self.cache.add_resource(new_resource)
        self.cache.remove(self.task_id)

        assert self._all_default_empty()
        assert self.cache.has_resource(new_resource)
        assert self.cache.get_by_path(new_resource.path) == new_resource
        assert self.cache.get_by_hash(new_resource.hash) == new_resource

    def test_clear(self):
        self._add_all()
        self.cache.clear()
        assert self._all_default_empty()

    def _add_all(self):
        resource = Resource(
            self.resource_hash,
            task_id=self.task_id,
            path=self.resource_path,
            files=['file']
        )
        self.cache.add_resource(resource)
        self.cache.set_prefix(self.task_id, self.prefix)

    def _all_default_empty(self):
        return self.cache.get_by_path(self.resource_hash) is None and \
            self.cache.get_by_hash(self.resource_path) is None and \
            self.cache.get_prefix(self.task_id) == '' and \
            self.cache.get_resources(self.task_id) == []


class TestResourceStorage(ResourceSetUp):

    def setUp(self):
        super().setUp()
        self.storage = ResourceStorage(
            self.dir_manager,
            self.dir_manager.get_task_resource_dir
        )

    def test_get_root(self):
        dir_manager_root = self.dir_manager.get_node_dir().rstrip(os.path.sep)
        storage_root = self.storage.get_root().rstrip(os.path.sep)

        assert dir_manager_root == storage_root
        assert dir_manager_root == self.storage.get_root().rstrip(os.path.sep)

    def test_get_dir(self):
        task_dir = self.storage.get_dir(self.task_id)

        assert os.path.isdir(task_dir)
        assert task_dir == self.dir_manager.get_task_resource_dir(self.task_id)
        assert task_dir != self.storage.get_dir(self.task_id + "-other")

    def test_get_path(self):
        valid = self.storage.get_path(self.test_dir_file, self.task_id)
        assert valid is not None
        assert os.path.exists(valid)

    def test_get_path_invalid(self):
        invalid = self.storage.get_path(self.test_dir_file + '_2', self.task_id)
        assert invalid is not None
        assert not os.path.exists(invalid)

    def test_relative_path(self):
        task_dir = self.storage.get_dir(self.task_id)
        self.storage.cache.set_prefix(self.task_id, task_dir)

        src_path = os.path.join('C:\\', 'some', 'path')
        assert self.storage.relative_path(src_path, self.task_id) == src_path
        assert self.storage.relative_path(src_path, self.task_id + '_2') == \
            src_path

        src_path = os.path.join('some', 'path')
        assert self.storage.relative_path(src_path, self.task_id) == src_path
        assert self.storage.relative_path(src_path, self.task_id + '_2') == \
            src_path

        src_path = os.path.join(task_dir, 'dir', 'file')
        assert self.storage.relative_path(src_path, self.task_id) == \
            os.path.join('dir', 'file')

    def test_copy(self):

        task_dir = self.storage.get_dir(self.task_id)
        self.storage.cache.set_prefix(self.task_id, task_dir)
        new_category = str(uuid.uuid4())

        for file_path in self.target_resources:

            relative_path = self.storage.relative_path(file_path, self.task_id)
            dst_path = self.storage.get_path(relative_path, new_category)

            assert file_path != dst_path
            self.storage.copy(file_path, relative_path, new_category)
            assert os.path.exists(dst_path)
