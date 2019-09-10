import uuid
import os

from unittest.mock import Mock, patch

from golem.resource.dirmanager import DirManager
from golem.resource.hyperdrive.resourcesmanager import DummyResourceManager
from golem.task.result.resultmanager import EncryptedResultPackageManager
from golem.task.result.resultpackage import ExtractedPackage
from golem.tools.testdirfixture import TestDirFixture

from tests.factories.hyperdrive import hyperdrive_client_kwargs


class MockTaskResult:
    def __init__(self, task_id, result,
                 owner_key_id=None, owner=None):

        if owner_key_id is None:
            owner_key_id = str(uuid.uuid4())
        if owner is None:
            owner = str(uuid.uuid4())

        self.task_id = task_id
        self.subtask_id = task_id
        self.result = result
        self.owner_key_id = owner_key_id
        self.owner = owner


def create_package(result_manager, node_name, task_id):
    rm = result_manager.resource_manager

    res_dir = rm.storage.get_dir(task_id)
    out_dir = os.path.join(res_dir, 'out_dir')
    out_dir_file = os.path.join(out_dir, 'dir_file')
    out_file = os.path.join(res_dir, 'out_file')

    os.makedirs(out_dir, exist_ok=True)
    with open(out_file, 'w') as f:
        f.write("File contents")
    with open(out_dir_file, 'w') as f:
        f.write("Dir file contents")

    files = [out_file, out_dir_file]
    rm.add_files(files, task_id)

    client_options = Mock(size=1024, timeout=10.)
    secret = result_manager.gen_secret()
    result = result_manager.create(
        task_result=MockTaskResult(
            task_id,
            [rm.storage.relative_path(f, task_id) for f in files]
        ),
        client_options=client_options,
        key_or_secret=secret
    )

    return result, secret


class TestEncryptedResultPackageManager(TestDirFixture):

    node_name = 'test_suite'

    def setUp(self):
        TestDirFixture.setUp(self)

        self.task_id = str(uuid.uuid4())
        self.dir_manager = DirManager(self.path)
        self.resource_manager = DummyResourceManager(
            self.dir_manager,
            resource_dir_method=self.dir_manager.get_task_output_dir,
            **hyperdrive_client_kwargs(),
        )

    def testGenSecret(self):
        manager = EncryptedResultPackageManager(self.resource_manager)
        secret = manager.gen_secret()

        self.assertIsInstance(secret, bytes)
        secret_len = len(secret)
        s_min = EncryptedResultPackageManager.min_secret_len
        s_max = EncryptedResultPackageManager.max_secret_len
        self.assertTrue(s_min <= secret_len <= s_max)

    def testCreate(self):
        manager = EncryptedResultPackageManager(self.resource_manager)
        data, secret = create_package(manager, self.node_name, self.task_id)
        content_hash, path, sha1, size, package_path = data

        self.assertIsNotNone(sha1)
        self.assertIsInstance(sha1, str)
        self.assertIsInstance(path, str)
        self.assertIsInstance(size, int)
        self.assertIsInstance(package_path, str)
        self.assertTrue(os.path.isfile(path))
        self.assertTrue(os.path.isfile(package_path))

    def testCreateEnvironmentError(self):
        manager = EncryptedResultPackageManager(self.resource_manager)
        manager.resource_manager.add_file = Mock()

        with self.assertRaises(EnvironmentError):
            create_package(manager, self.node_name, self.task_id)

    def testCreateUnexpectedError(self):
        manager = EncryptedResultPackageManager(self.resource_manager)
        manager.resource_manager.add_file = Mock()

        with patch('os.path.exists', return_value=False):
            with self.assertRaises(Exception) as exc:
                assert not isinstance(exc, EnvironmentError)
                create_package(manager, self.node_name, self.task_id)

    def testExtract(self):
        manager = EncryptedResultPackageManager(self.resource_manager)
        data, secret = create_package(manager, self.node_name, self.task_id)
        _, path, __, ___, ____ = data

        extracted = manager.extract(path, key_or_secret=secret)
        self.assertIsInstance(extracted, ExtractedPackage)

        for f in extracted.files:
            assert os.path.exists(os.path.join(extracted.files_dir, f))

    def testPullPackage(self):
        manager = EncryptedResultPackageManager(self.resource_manager)
        data, secret = create_package(manager, self.node_name, self.task_id)
        content_hash, path, _, _, _ = data

        assert os.path.exists(path)
        assert content_hash

        def success(*args, **kwargs):
            pass

        def error(exc, *args, **kwargs):
            self.fail("Error downloading package: {}".format(exc))

        dir_manager = DirManager(self.path)
        resource_manager = DummyResourceManager(
            dir_manager,
            resource_dir_method=dir_manager.get_task_temporary_dir,
            **hyperdrive_client_kwargs(),
        )

        new_manager = EncryptedResultPackageManager(resource_manager)
        new_manager.pull_package(content_hash, self.task_id, self.task_id,
                                 secret,
                                 success=success,
                                 error=error,
                                 async_=False)
