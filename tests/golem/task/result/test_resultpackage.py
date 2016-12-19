import os
import shutil
import uuid

from golem.core.fileencrypt import FileEncryptor
from golem.resource.dirmanager import DirManager
from golem.task.result.resultpackage import ZipPackager, EncryptingPackager, EncryptingTaskResultPackager, \
    ExtractedPackage
from golem.task.taskbase import result_types
from golem.tools.testdirfixture import TestDirFixture

node_name = 'test_suite'


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


class MockDirContents(object):

    @staticmethod
    def populate(dest_obj, dir_manager, task_id):
        res_dir = dir_manager.get_task_temporary_dir(task_id)

        out_file = os.path.join(res_dir, 'out_file')
        out_dir = os.path.join(res_dir, 'out_dir')
        out_dir_file = os.path.join(out_dir, 'dir_file')

        files = [out_file, out_dir_file]
        pickle_files = [('pickle1', 'pickle_data1'), ('pickle2', 'pickle_data2')]

        with open(out_file, 'w') as f:
            f.write("File contents")

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)

        with open(out_dir_file, 'w') as f:
            f.write("Dir file contents")

        dest_obj.file_list = MockDirContents.create_file_list(files, pickle_files)
        dest_obj.res_dir = res_dir
        dest_obj.files = files
        dest_obj.pickle_files = pickle_files
        dest_obj.out_dir = dest_obj.dir_manager.get_task_temporary_dir(task_id + '-extracted')
        dest_obj.out_path = os.path.join(dest_obj.out_dir, str(uuid.uuid4()))

    @staticmethod
    def create_file_list(files, pickle_files):
        return [os.path.basename(f) for f in files] + [p[0] for p in pickle_files]


class TestZipPackager(TestDirFixture):

    def setUp(self):
        TestDirFixture.setUp(self)

        self.task_id = str(uuid.uuid4())
        self.dir_manager = DirManager(self.path)
        MockDirContents.populate(self, self.dir_manager, self.task_id)

    def testCreate(self):
        zp = ZipPackager()
        path = zp.create(self.out_path, self.files, self.pickle_files)

        self.assertTrue(os.path.exists(path))
        os.remove(path)

    def testExtract(self):
        zp = ZipPackager()
        zp.create(self.out_path, self.files, self.pickle_files)
        files, out_dir = zp.extract(self.out_path)

        self.assertTrue(len(files) == len(self.file_list))
        shutil.rmtree(out_dir)


class TestEncryptingPackager(TestDirFixture):

    def setUp(self):
        TestDirFixture.setUp(self)

        self.task_id = str(uuid.uuid4())
        self.dir_manager = DirManager(self.path)
        self.secret = FileEncryptor.gen_secret(10, 20)
        MockDirContents.populate(self, self.dir_manager, self.task_id)

    def testCreate(self):
        ep = EncryptingPackager(self.secret)
        path = ep.create(self.out_path, self.files, self.pickle_files)

        self.assertTrue(os.path.exists(path))
        os.remove(path)

    def testExtract(self):
        ep = EncryptingPackager(self.secret)
        ep.create(self.out_path, self.files, self.pickle_files)
        files, outdir = ep.extract(self.out_path)

        self.assertTrue(len(files) == len(self.file_list))
        shutil.rmtree(self.out_dir)


class TestEncryptingTaskResultPackager(TestDirFixture):

    def setUp(self):
        TestDirFixture.setUp(self)

        self.task_id = str(uuid.uuid4())
        self.dir_manager = DirManager(self.path)
        self.secret = FileEncryptor.gen_secret(10, 20)
        MockDirContents.populate(self, self.dir_manager, self.task_id)

    def testCreate(self):
        etp = EncryptingTaskResultPackager(self.secret)
        node = MockNode(node_name)

        tr = MockTaskResult(self.task_id, self.files)
        path = etp.create(self.out_path,
                          node=node,
                          task_result=tr,
                          cbor_files=self.pickle_files)

        self.assertTrue(os.path.exists(path))
        os.remove(path)

        tr = MockTaskResult(self.task_id, "Result string data",
                            result_type=result_types["data"])

        path = etp.create(self.out_path,
                          node=node,
                          task_result=tr)

        self.assertTrue(os.path.exists(path))
        os.remove(path)

    def testExtract(self):
        etp = EncryptingTaskResultPackager(self.secret)
        node = MockNode(node_name)
        tr = MockTaskResult(self.task_id, self.files)

        path = etp.create(self.out_path,
                          node=node,
                          task_result=tr,
                          cbor_files=self.pickle_files)

        extracted = etp.extract(path)

        self.assertIsInstance(extracted, ExtractedPackage)
        self.assertEqual(len(extracted.files), len(self.file_list))

        shutil.rmtree(extracted.files_dir)


class TestExtractedPackage(TestDirFixture):

    def setUp(self):
        TestDirFixture.setUp(self)

        self.task_id = str(uuid.uuid4())
        self.dir_manager = DirManager(self.path)
        self.secret = FileEncryptor.gen_secret(10, 20)
        MockDirContents.populate(self, self.dir_manager, self.task_id)

    def testToExtraData(self):
        etp = EncryptingTaskResultPackager(self.secret)
        node = MockNode(node_name)
        tr = MockTaskResult(self.task_id, self.files)

        path = etp.create(self.out_path,
                          node=node,
                          task_result=tr,
                          cbor_files=self.pickle_files)

        extracted = etp.extract(path)
        extra_data = extracted.to_extra_data()

        self.assertEqual(extra_data.get('result_type', None), result_types['files'])
        self.assertEqual(len(extra_data.get('result', [])), len(self.file_list))
        self.assertIsNone(extra_data.get('data_type', None))

        for filename in extra_data.get('result', []):
            self.assertTrue(os.path.exists(filename))

        os.remove(path)
        shutil.rmtree(extracted.files_dir)







