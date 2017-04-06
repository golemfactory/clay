import os
import unittest
import uuid

from mock import patch

from golem.resource.base.resourcesmanager import ResourceCache, ResourceStorage, TestResourceManager, FileResource
from golem.resource.dirmanager import DirManager
from golem.tools.testdirfixture import TestDirFixture


class _Common(object):

    class ResourceSetUp(TestDirFixture):

        def setUp(self):
            TestDirFixture.setUp(self)

            self.node_name = str(uuid.uuid4())
            self.task_id = str(uuid.uuid4())
            self.dir_manager = DirManager(self.path)

            self.resources_dir = self.dir_manager.get_task_resource_dir(self.task_id)
            self.test_file = os.path.join(self.resources_dir, 'test_file.one.two')
            self.test_dir = os.path.join(self.resources_dir, 'test_dir.one.two')
            self.test_dir_file = os.path.join(self.test_dir, 'dir_file.one.two')

            self.split_resources = [
                ['test_file.one.two'],
                ['test_dir.one.two', 'dir_file.one.two']
            ]
            self.joined_resources = [
                os.path.join(*r) for r in self.split_resources
            ]
            self.target_resources = [
                os.path.join(self.resources_dir, *self.split_resources[0]),
                os.path.join(self.resources_dir, *self.split_resources[1])
            ]

            if not os.path.isdir(self.test_dir):
                os.makedirs(self.test_dir)

            open(self.test_file, 'w').close()
            with open(self.test_dir_file, 'w') as f:
                f.write("test content")


class TestResourceCache(unittest.TestCase):

    def setUp(self):
        self.cache = ResourceCache()
        self.resource_path = unicode(os.path.join('abstract', 'prefix', 'path'))
        self.resource_name = u'\0!abstract_name\0!'
        self.resource_hash = str(uuid.uuid4())
        self.prefix = unicode(os.path.join('abstract', 'prefix'))
        self.task_id = u'\0!abstract\0!'

    def test_prefix(self):
        self.cache.set_prefix(self.task_id, self.prefix)
        resource = FileResource(self.resource_name, self.resource_hash,
                                task_id=self.task_id, path=self.resource_path)

        assert self.cache.get_prefix(resource.task_id) == self.prefix
        assert self.cache.get_prefix(str(uuid.uuid4())) == ''
        assert self.cache.get_prefix(str(uuid.uuid4()), 'default_value') == 'default_value'

        self.cache.add_resource(resource)
        self.cache.remove(resource.task_id)
        assert self.cache.get_prefix(resource.task_id) == ''

    def test_resources(self):
        resource = FileResource(self.resource_name, self.resource_hash,
                                task_id=self.task_id, path=self.resource_path)
        new_task_id = str(uuid.uuid4())
        new_resource = FileResource('new_name', str(uuid.uuid4()), new_task_id)
        tmp_task_id = str(uuid.uuid4())
        tmp_resource = FileResource('tmp_name', str(uuid.uuid4()), tmp_task_id)

        self.cache.add_resource(resource)
        self.cache.add_resource(new_resource)

        assert self.cache.get_resources(self.task_id) == [resource]
        assert self.cache.get_resources(new_task_id) == [new_resource]
        assert self.cache.get_resources('unknown') == []
        assert self.cache.has_resource(resource)
        assert self.cache.has_resource(new_resource)
        assert not self.cache.has_resource(tmp_resource)

        self.cache.add_resource(tmp_resource)

        assert self.cache.get_resources(self.task_id) == [resource]
        assert self.cache.get_resources(tmp_task_id) == [tmp_resource]

        assert self.cache.remove(self.task_id)
        assert self.cache.remove('unknown') == []
        assert self.cache.get_resources(new_task_id) == [new_resource]

    def test_remove(self):
        self._add_all()
        self.cache.remove(self.task_id)
        assert self._all_default_empty()

        new_hash = str(uuid.uuid4())
        new_path = '/other/path'
        new_task = str(uuid.uuid4())
        new_resource = FileResource(new_path, new_hash,
                                    task_id=new_task, path=new_path)

        self._add_all()
        self.cache.add_resource(new_resource)
        self.cache.remove(self.task_id)

        assert self._all_default_empty()
        assert self.cache.has_resource(new_resource)
        assert self.cache.get_by_path(new_path) == new_resource
        assert self.cache.get_by_hash(new_hash) == new_resource

    def test_clear(self):
        self._add_all()
        self.cache.clear()
        assert self._all_default_empty()

    def _add_all(self):
        resource = FileResource(self.resource_path, self.resource_hash,
                                task_id=self.task_id, path=self.resource_path)
        self.cache.add_resource(resource)
        self.cache.set_prefix(self.task_id, self.prefix)

    def _all_default_empty(self):
        return self.cache.get_by_path(self.resource_hash) is None and \
            self.cache.get_by_hash(self.resource_path) is None and \
            self.cache.get_prefix(self.task_id) == '' and \
            self.cache.get_resources(self.task_id) == []


class TestResourceStorage(_Common.ResourceSetUp):

    def setUp(self):
        _Common.ResourceSetUp.setUp(self)
        self.storage = ResourceStorage(self.dir_manager,
                                       self.dir_manager.get_task_resource_dir)

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
        invalid = self.storage.get_path(self.test_dir_file + '_2', self.task_id)

        assert valid is not None
        assert os.path.exists(valid)

        assert invalid is not None
        assert not os.path.exists(invalid)

    def test_relative_path(self):
        task_dir = self.storage.get_dir(self.task_id)
        self.storage.cache.set_prefix(self.task_id, task_dir)

        src_path = os.path.join('C:\\', 'some', 'path')
        assert self.storage.relative_path(src_path, self.task_id) == src_path
        assert self.storage.relative_path(src_path, self.task_id + '_2') == src_path

        src_path = os.path.join('some', 'path')
        assert self.storage.relative_path(src_path, self.task_id) == src_path
        assert self.storage.relative_path(src_path, self.task_id + '_2') == src_path

        src_path = os.path.join(task_dir, 'dir', 'file')
        assert self.storage.relative_path(src_path, self.task_id) == os.path.join('dir', 'file')

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


class TestAbstractResourceManager(_Common.ResourceSetUp):

    def setUp(self):
        _Common.ResourceSetUp.setUp(self)
        self.resource_manager = TestResourceManager(self.dir_manager)

    def test_copy_files(self):
        old_resource_dir = self.resource_manager.storage.get_root()
        prev_content = os.listdir(old_resource_dir)

        self.dir_manager.node_name = "another" + self.node_name
        self.resource_manager.copy_files(old_resource_dir)

        assert os.listdir(self.resource_manager.storage.get_root()) == prev_content

    def test_add_file(self):
        self.resource_manager.storage.clear_cache()

        self.resource_manager.add_file(self.test_dir_file, self.task_id)
        resources = self.resource_manager.storage.get_resources(self.task_id)
        assert len(resources) == 1

        with self.assertRaises(RuntimeError):
            self.resource_manager.add_files(['/.!&^%'], self.task_id)

        resources = self.resource_manager.storage.get_resources(self.task_id)
        assert len(resources) == 1

    def test_add_files(self):
        self.resource_manager.storage.clear_cache()
        self.resource_manager.add_files(self.target_resources, self.task_id,
                                        absolute_path=True)

        storage = self.resource_manager.storage
        resources = storage.get_resources(self.task_id)

        assert resources
        assert all([r.file_name in self.target_resources for r in resources])

        for resource in resources:
            assert storage.cache.get_by_path(resource.file_name) is not None
        assert storage.cache.get_by_path(str(uuid.uuid4())) is None

        storage.clear_cache()

        self.resource_manager.add_files([self.test_dir_file], self.task_id)
        assert len(storage.get_resources(self.task_id)) == 1

        with self.assertRaises(RuntimeError):
            self.resource_manager.add_files(['/.!&^%'], self.task_id)

        assert len(storage.get_resources(self.task_id)) == 1

    def test_add_task(self):
        storage = self.resource_manager.storage
        storage.clear_cache()

        resource_paths = [storage.get_path(r, self.task_id) for r in self.target_resources]

        self.resource_manager._add_task(resource_paths, self.task_id)
        resources = storage.get_resources(self.task_id)

        assert len(resources) == len(self.target_resources)
        assert storage.cache.get_prefix(self.task_id)
        assert storage.cache.get_resources(self.task_id)

        new_task = str(uuid.uuid4())
        self.resource_manager._add_task(resource_paths, new_task)
        assert len(resources) == len(storage.get_resources(new_task))

        self.resource_manager._add_task(resource_paths, new_task)
        assert len(storage.get_resources(new_task)) == len(resources)

    def test_remove_task(self):
        self.resource_manager.storage.clear_cache()

        resource_paths = [self.resource_manager.storage.get_path(r, self.task_id) for r in self.target_resources]
        self.resource_manager._add_task(resource_paths, self.task_id)
        self.resource_manager.remove_task(self.task_id)

        assert not self.resource_manager.storage.cache.get_prefix(self.task_id)
        assert not self.resource_manager.storage.get_resources(self.task_id)

    def test_command_failed(self):
        with patch('golem.resource.base.resourcesmanager.logger') as logger:
            self.resource_manager.command_failed(Exception('Unknown error'),
                                                 self.resource_manager.commands.id,
                                                 str(uuid.uuid4()))
            assert logger.error.called

    def test_to_from_wire(self):

        entries = [FileResource(r, str(uuid.uuid4()), task_id="task", path=r)
                   for r in self.joined_resources]

        resources_split = self.resource_manager.to_wire(entries)
        resources_joined = self.resource_manager.from_wire(resources_split)

        assert len(entries) == len(self.target_resources)
        assert all([r[0] in self.split_resources for r in resources_split])
        assert all([r[0] in self.joined_resources for r in resources_joined])

        entries = [
            ['resource', '1'],
            [None, '2'],
            None,
            [['split', 'path'], '4']
        ]
        assert self.resource_manager.from_wire(entries) == [
            ['resource', '1'],
            [os.path.join('split', 'path'), '4']
        ]
