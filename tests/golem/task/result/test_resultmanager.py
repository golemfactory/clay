import os
import uuid

from golem.resource.base.resourcesmanager import TestResourceManager
from golem.resource.dirmanager import DirManager
from golem.task.result.resultmanager import EncryptedResultPackageManager
from golem.task.result.resultpackage import ExtractedPackage
from golem.task.taskbase import result_types
from golem.tools.testdirfixture import TestDirFixture


class MockNode:
    def __init__(self, name, key=None):
        if not key:
            key = uuid.uuid4()

        self.node_name = name
        self.key = key


class MockTaskResult:
    def __init__(self, task_id, result, result_type=None,
                 owner_key_id=None, owner=None):

        if result_type is None:
            result_type = result_types['files']
        if owner_key_id is None:
            owner_key_id = str(uuid.uuid4())
        if owner is None:
            owner = str(uuid.uuid4())

        self.task_id = task_id
        self.subtask_id = task_id
        self.result = result
        self.result_type = result_type
        self.owner_key_id = owner_key_id
        self.owner = owner


class TestEncryptedResultPackageManager(TestDirFixture):

    node_name = 'test_suite'

    class TestPackageCreator(object):
        @staticmethod
        def create(result_manager, node_name, task_id):
            rm = result_manager.resource_manager
            res_dir = rm.storage.get_dir(task_id)

            out_file = os.path.join(res_dir, 'out_file')
            out_dir = os.path.join(res_dir, 'out_dir')
            out_dir_file = os.path.join(out_dir, 'dir_file')
            files = [out_file, out_dir_file]

            with open(out_file, 'w') as f:
                f.write("File contents")

            if not os.path.isdir(out_dir):
                os.makedirs(out_dir)

            with open(out_dir_file, 'w') as f:
                f.write("Dir file contents")

            rm.add_files(files, task_id)

            secret = result_manager.gen_secret()
            mock_node = MockNode(node_name)
            mock_task_result = MockTaskResult(task_id, files)

            return result_manager.create(mock_node,
                                         mock_task_result,
                                         key_or_secret=secret), secret

    def setUp(self):
        TestDirFixture.setUp(self)

        self.task_id = str(uuid.uuid4())
        self.dir_manager = DirManager(self.path)
        self.resource_manager = TestResourceManager(self.dir_manager,
                                                    resource_dir_method=self.dir_manager.get_task_output_dir)

    def testGenSecret(self):
        manager = EncryptedResultPackageManager(self.resource_manager)
        secret = manager.gen_secret()

        self.assertIsInstance(secret, basestring)
        secret_len = len(secret)
        s_min = EncryptedResultPackageManager.min_secret_len
        s_max = EncryptedResultPackageManager.max_secret_len
        self.assertTrue(s_min <= secret_len <= s_max)

    def testCreate(self):
        manager = EncryptedResultPackageManager(self.resource_manager)
        data, secret = self.TestPackageCreator.create(manager,
                                                      self.node_name,
                                                      self.task_id)
        path, multihash = data

        self.assertIsInstance(path, basestring)
        self.assertTrue(os.path.isfile(path))

    def testExtract(self):
        manager = EncryptedResultPackageManager(self.resource_manager)
        data, secret = self.TestPackageCreator.create(manager,
                                                      self.node_name,
                                                      self.task_id)
        path, multihash = data

        extracted = manager.extract(path, key_or_secret=secret)
        self.assertIsInstance(extracted, ExtractedPackage)

        for f in extracted.files:
            self.assertTrue(os.path.exists(os.path.join(extracted.files_dir, f)))

    def testPullPackage(self):
        manager = EncryptedResultPackageManager(self.resource_manager)
        data, secret = self.TestPackageCreator.create(manager,
                                                      self.node_name,
                                                      self.task_id)
        path, multihash = data

        assert os.path.exists(path)
        assert multihash

        def success(*args, **kwargs):
            pass

        def error(exc, *args, **kwargs):
            self.fail("Error downloading package: {}".format(exc))

        dir_manager = DirManager(self.path)
        resource_manager = TestResourceManager(dir_manager,
                                               resource_dir_method=dir_manager.get_task_temporary_dir)

        new_manager = EncryptedResultPackageManager(resource_manager)
        new_manager.pull_package(multihash, self.task_id, self.task_id,
                                 secret,
                                 success=success,
                                 error=error,
                                 async=False)
