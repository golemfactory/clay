import uuid
import os

from unittest.mock import Mock

from golem.core.fileencrypt import FileEncryptor
from golem.resource.dirmanager import DirManager
from golem.task.result.resultpackage import EncryptingPackager, \
    EncryptingTaskResultPackager, ExtractedPackage, ZipPackager, backup_rename
from golem.task.taskbase import ResultType
from golem.testutils import TempDirFixture


def mock_node():
    return Mock(name='test_node', key=uuid.uuid4())


def mock_task_result(task_id, result, result_type=None):
    if result_type is None:
        result_type = ResultType.FILES

    return Mock(
        task_id=task_id,
        subtask_id=task_id,
        result=result,
        result_type=result_type,
        owner_key_id=str(uuid.uuid4()),
        owner=str(uuid.uuid4())
    )


class PackageDirContentsFixture(TempDirFixture):

    def setUp(self):
        super().setUp()

        task_id = str(uuid.uuid4())
        dir_manager = DirManager(self.path)

        res_dir = dir_manager.get_task_temporary_dir(task_id)
        out_dir = os.path.join(res_dir, 'out_dir')
        out_dir_file = os.path.join(out_dir, 'dir_file')
        out_file = os.path.join(res_dir, 'out_file')

        memory_files = [('mem1', 'data1'), ('mem2', 'data2')]

        os.makedirs(out_dir, exist_ok=True)

        with open(out_file, 'w') as f:
            f.write("File contents")
        with open(out_dir_file, 'w') as f:
            f.write("Dir file contents")

        self.dir_manager = dir_manager
        self.task_id = task_id
        self.secret = FileEncryptor.gen_secret(10, 20)

        self.disk_files = [out_file, out_dir_file]
        self.memory_files = memory_files

        disk_file_names = [os.path.basename(f) for f in self.disk_files]
        memory_file_names = [p[0] for p in self.memory_files]
        self.all_files = disk_file_names + memory_file_names

        self.res_dir = res_dir
        self.out_dir = out_dir
        self.out_path = os.path.join(self.out_dir, str(uuid.uuid4()))


class TestZipPackager(PackageDirContentsFixture):

    def testCreate(self):
        zp = ZipPackager()
        path, _ = zp.create(self.out_path, self.disk_files, self.memory_files)

        self.assertTrue(os.path.exists(path))

    def testExtract(self):
        zp = ZipPackager()
        zp.create(self.out_path, self.disk_files, self.memory_files)
        files, out_dir = zp.extract(self.out_path)

        self.assertTrue(len(files) == len(self.all_files))


class TestEncryptingPackager(PackageDirContentsFixture):

    def testCreate(self):
        ep = EncryptingPackager(self.secret)
        path, _ = ep.create(self.out_path, self.disk_files, self.memory_files)

        self.assertTrue(os.path.exists(path))

    def testExtract(self):
        ep = EncryptingPackager(self.secret)
        ep.create(self.out_path, self.disk_files, self.memory_files)
        files, _ = ep.extract(self.out_path)

        self.assertTrue(len(files) == len(self.all_files))


class TestEncryptingTaskResultPackager(PackageDirContentsFixture):

    def testCreate(self):
        etp = EncryptingTaskResultPackager(self.secret)
        node = mock_node()

        tr = mock_task_result(self.task_id, self.disk_files)
        path, _ = etp.create(self.out_path,
                             node=node,
                             task_result=tr,
                             cbor_files=self.memory_files)

        self.assertTrue(os.path.exists(path))

    def testCreateData(self):
        etp = EncryptingTaskResultPackager(self.secret)
        node = mock_node()

        tr = mock_task_result(self.task_id, "Result string data",
                              result_type=ResultType.DATA)

        path, _ = etp.create(self.out_path,
                             node=node,
                             task_result=tr)

        self.assertTrue(os.path.exists(path))

    def testExtract(self):
        etp = EncryptingTaskResultPackager(self.secret)
        node = mock_node()
        tr = mock_task_result(self.task_id, self.disk_files)

        path, _ = etp.create(self.out_path,
                             node=node,
                             task_result=tr,
                             cbor_files=self.memory_files)

        extracted = etp.extract(path)

        self.assertIsInstance(extracted, ExtractedPackage)
        self.assertEqual(len(extracted.files), len(self.all_files))


class TestExtractedPackage(PackageDirContentsFixture):

    def testToExtraData(self):
        etp = EncryptingTaskResultPackager(self.secret)
        node = mock_node()
        tr = mock_task_result(self.task_id, self.disk_files)

        path, _ = etp.create(self.out_path,
                             node=node,
                             task_result=tr,
                             cbor_files=self.memory_files)

        extracted = etp.extract(path)
        extra_data = extracted.to_extra_data()

        self.assertEqual(extra_data.get('result_type', None), ResultType.FILES)
        self.assertEqual(len(extra_data.get('result', [])), len(self.all_files))
        self.assertIsNone(extra_data.get('data_type', None))

        for filename in extra_data.get('result', []):
            self.assertTrue(os.path.exists(filename))


class TestBackupRename(TempDirFixture):

    FILE_CONTENTS = 'Test file contents'

    def test(self):
        file_dir = os.path.join(self.path, 'directory')
        file_path = os.path.join(file_dir, 'file')
        os.makedirs(file_dir, exist_ok=True)

        def create_file():
            with open(file_path, 'w') as f:
                f.write(self.FILE_CONTENTS)

        def file_count():
            return len(os.listdir(file_dir))

        def file_contents(num):
            with open(file_path + '.{}'.format(num)) as f:
                return f.read().strip()

        backup_rename(file_path)
        assert file_count() == 0

        create_file()

        assert file_count() == 1
        backup_rename(file_path, max_iterations=2)
        assert file_count() == 1
        assert file_contents(1) == self.FILE_CONTENTS

        create_file()

        backup_rename(file_path, max_iterations=2)
        assert file_count() == 2
        assert file_contents(1) == self.FILE_CONTENTS
        assert file_contents(2) == self.FILE_CONTENTS

        create_file()

        backup_rename(file_path, max_iterations=2)
        assert file_count() == 3

        files = os.listdir(file_dir)
        files.remove('file.1')
        files.remove('file.2')

        with open(os.path.join(file_dir, files[0])) as f:
            assert f.read().strip() == self.FILE_CONTENTS
