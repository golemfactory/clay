import uuid
from os import makedirs, listdir
from os.path import basename, exists, join, relpath
from pathlib import Path

from golem.core.fileencrypt import FileEncryptor
from golem.resource.dirmanager import DirManager
from golem.task.result.resultpackage import EncryptingPackager, \
    EncryptingTaskResultPackager, ExtractedPackage, ZipPackager, backup_rename
from golem.testutils import TempDirFixture


class PackageDirContentsFixture(TempDirFixture):

    def setUp(self):
        super().setUp()

        task_id = str(uuid.uuid4())
        dir_manager = DirManager(self.path)

        res_dir = dir_manager.get_task_temporary_dir(task_id)
        out_dir = join(res_dir, 'out_dir')
        out_dir_file = join(out_dir, 'dir_file')
        out_file = join(res_dir, 'out_file')

        makedirs(out_dir, exist_ok=True)

        with open(out_file, 'w') as f:
            f.write("File contents")
        with open(out_dir_file, 'w') as f:
            f.write("Dir file contents")

        self.dir_manager = dir_manager
        self.task_id = task_id
        self.secret = FileEncryptor.gen_secret(10, 20)

        self.disk_files = [out_file, out_dir_file]
        self.all_files = list(map(basename, self.disk_files))

        self.res_dir = res_dir
        self.out_dir = out_dir
        self.out_path = join(self.out_dir, str(uuid.uuid4()))


class TestZipPackager(PackageDirContentsFixture):

    def testCreate(self):
        zp = ZipPackager()
        path, _ = zp.create(self.out_path, self.disk_files)

        self.assertTrue(exists(path))

    def testExtract(self):
        zp = ZipPackager()
        zp.create(self.out_path, self.disk_files)
        files, out_dir = zp.extract(self.out_path)

        self.assertEqual(len(files), len(self.all_files))
        self.assertTrue(all(exists(join(self.out_dir, f)) for f in files))


# pylint: disable=too-many-instance-attributes
class TestZipDirectoryPackager(TempDirFixture):
    def setUp(self):
        super().setUp()

        task_id = str(uuid.uuid4())
        dir_manager = DirManager(self.path)

        res_dir = dir_manager.get_task_temporary_dir(task_id)
        out_dir = join(res_dir, 'out_dir')

        self.dir_manager = dir_manager
        self.task_id = task_id
        self.secret = FileEncryptor.gen_secret(10, 20)

        # Create directory structure:
        #    |-- directory
        #    |-- directory2
        #    |   |-- directory3
        #    |   |   `-- file3.txt
        #    |   `-- file2.txt
        #    `-- file.txt

        f0_path = join(res_dir, "file.txt")
        d1_path = join(res_dir, "directory")
        d2_path = join(res_dir, "directory2/")
        f2_path = join(d2_path, "file2.txt")
        d3_path = join(d2_path, "directory3/")
        f3_path = join(d3_path, "file3.txt")

        makedirs(out_dir, exist_ok=True)
        makedirs(d1_path, exist_ok=True)
        makedirs(d3_path, exist_ok=True)

        for path in [f0_path, f2_path, f3_path]:
            with open(path, 'w') as out:
                out.write("content")

        self.disk_files = [
            f0_path,
            d1_path,
            d2_path,
        ]

        self.expected_results = [
            basename(f0_path),
            basename(d1_path),
            relpath(d2_path, res_dir),
            relpath(d3_path, res_dir),
            relpath(f2_path, res_dir),
            relpath(f3_path, res_dir)
        ]

        self.res_dir = res_dir
        self.out_dir = out_dir
        self.out_path = join(self.path, str(uuid.uuid4()))

    def testCreate(self):
        zp = ZipPackager()
        path, _ = zp.create(self.out_path, self.disk_files)

        self.assertTrue(exists(path))

    def testExtract(self):
        zp = ZipPackager()
        zp.create(self.out_path, self.disk_files)

        files, _ = zp.extract(self.out_path, self.out_dir)
        files = [str(Path(f)) for f in files]

        self.assertTrue(set(files) == set(self.expected_results))
        self.assertTrue(all(exists(join(self.out_dir, f)) for f in files))


class TestEncryptingPackager(PackageDirContentsFixture):

    def testCreate(self):
        ep = EncryptingPackager(self.secret)
        path, _ = ep.create(self.out_path, self.disk_files)

        self.assertTrue(exists(path))

    def testExtract(self):
        ep = EncryptingPackager(self.secret)
        ep.create(self.out_path, self.disk_files)
        files, _ = ep.extract(self.out_path)

        self.assertTrue(len(files) == len(self.all_files))


class TestEncryptingTaskResultPackager(PackageDirContentsFixture):

    def testCreate(self):
        etp = EncryptingTaskResultPackager(self.secret)

        path, _ = etp.create(self.out_path,
                             disk_files=self.disk_files)

        self.assertTrue(exists(path))

    def testExtract(self):
        etp = EncryptingTaskResultPackager(self.secret)

        path, _ = etp.create(self.out_path,
                             disk_files=self.disk_files)

        extracted = etp.extract(path)

        self.assertIsInstance(extracted, ExtractedPackage)
        self.assertEqual(len(extracted.files), len(self.all_files))


class TestExtractedPackage(PackageDirContentsFixture):

    def testToExtraData(self):
        etp = EncryptingTaskResultPackager(self.secret)

        path, _ = etp.create(self.out_path,
                             disk_files=self.disk_files)

        extracted = etp.extract(path)
        full_path_files = extracted.get_full_path_files()

        self.assertEqual(len(full_path_files), len(self.all_files))

        for filename in full_path_files:
            self.assertTrue(exists(filename))


class TestBackupRename(TempDirFixture):

    FILE_CONTENTS = 'Test file contents'

    def test(self):
        file_dir = join(self.path, 'directory')
        file_path = join(file_dir, 'file')
        makedirs(file_dir, exist_ok=True)

        def create_file():
            with open(file_path, 'w') as f:
                f.write(self.FILE_CONTENTS)

        def file_count():
            return len(listdir(file_dir))

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

        files = listdir(file_dir)
        files.remove('file.1')
        files.remove('file.2')

        with open(join(file_dir, files[0])) as f:
            assert f.read().strip() == self.FILE_CONTENTS
