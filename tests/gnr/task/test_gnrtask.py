import shutil
import os
import zlib
import cPickle as pickle

from mock import Mock

from golem.core.fileshelper import outer_dir_path
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import result_types
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture

from gnr.task.gnrtask import GNRTask, logger


class TestGNRTask(LogTestCase, TestDirFixture):
    def _get_gnr_task(self):
        task = GNRTask("src code", "ABC", "xyz", "10.10.10.10", 123, "key",
                       "environment", 3000, 30, 1024, 1024, 100)
        dm = DirManager(self.path)
        task.initialize(dm)
        return task

    def test_gnr_task(self):
        task = self._get_gnr_task()
        self.assertIsInstance(task, GNRTask)
        self.assertEqual(task.header.max_price, 100)

        subtask_id = "xxyyzz"

        task.subtasks_given[subtask_id] = Mock()
        self.assertEqual(task.get_stdout(subtask_id), "")
        self.assertEqual(task.get_stderr(subtask_id), "")
        self.assertEqual(task.get_results(subtask_id), [])

        task.stdout[subtask_id] = "stdout in string"
        task.stderr[subtask_id] = "stderr in string"
        task.results[subtask_id] = range(10)

        self.assertEqual(task.get_stdout(subtask_id), task.stdout[subtask_id])
        self.assertEqual(task.get_stderr(subtask_id), task.stderr[subtask_id])
        self.assertEqual(task.get_results(subtask_id), range(10))

        files = self.additional_dir_content([2])
        with open(files[0], 'w') as f:
            f.write("stdout in file")
        with open(files[1], 'w') as f:
            f.write("stderr in file")

        task.stdout[subtask_id] = files[0]
        task.stderr[subtask_id] = files[1]

        self.assertEqual(task.get_stdout(subtask_id), files[0])
        self.assertEqual(task.get_stderr(subtask_id), files[1])
        
        self.assertEqual(task.after_test(None, None), None)

    def test_interpret_task_results(self):
        task = self._get_gnr_task()

        subtask_id = "xxyyzz"
        files_dir = os.path.join(task.tmp_dir, subtask_id)
        files = self.additional_dir_content([5], sub_dir=files_dir)

        shutil.move(files[2], files[2]+".log")
        files[2] += ".log"
        shutil.move(files[3], files[3]+"err.log")
        files[3] += "err.log"

        task.interpret_task_results(subtask_id, files, result_types["files"])

        files[0] = outer_dir_path(files[0])
        files[1] = outer_dir_path(files[1])
        files[4] = outer_dir_path(files[4])

        self.assertEqual(task.results[subtask_id], [files[0], files[1], files[4]])
        self.assertEqual(task.stderr[subtask_id], files[3])
        self.assertEqual(task.stdout[subtask_id], files[2])

        for f in files:
            os.remove(f)
            self.assertFalse(os.path.isfile(f))

        subtask_id = "aabbcc"
        files_dir = os.path.join(task.tmp_dir, subtask_id)
        files = self.additional_dir_content([5], sub_dir=files_dir)

        shutil.move(files[2], files[2]+".log")
        files[2] += ".log"
        shutil.move(files[3], files[3]+"err.log")
        files[3] += "err.log"

        res = [self.__compress_and_pickle_file(files[0], "abc"*1000),
               self.__compress_and_pickle_file(files[1], "def"*100),
               self.__compress_and_pickle_file(files[2], "outputlog"),
               self.__compress_and_pickle_file(files[3], "errlog"),
               self.__compress_and_pickle_file(files[4], "ghi")]

        task.interpret_task_results(subtask_id, res, result_types["data"])

        files[0] = outer_dir_path(files[0])
        files[1] = outer_dir_path(files[1])
        files[4] = outer_dir_path(files[4])

        self.assertEqual(task.results[subtask_id], [files[0], files[1], files[4]])
        self.assertEqual(task.stderr[subtask_id], files[3])
        self.assertEqual(task.stdout[subtask_id], files[2])

        for f in [files[0], files[1], files[4]]:
            self.assertTrue(os.path.isfile(os.path.join(task.tmp_dir, os.path.basename(f))))

        for f in [files[2], files[3]]:
            self.assertTrue(os.path.isfile(os.path.join(task.tmp_dir, subtask_id, os.path.basename(f))))

        subtask_id = "112233"
        task.interpret_task_results(subtask_id, res, 58)
        self.assertEqual(task.results[subtask_id], [])
        self.assertEqual(task.stderr[subtask_id], "[GOLEM] Task result 58 not supported")
        self.assertEqual(task.stdout[subtask_id], "")

    def __compress_and_pickle_file(self, file_name, data):
        file_data = zlib.compress(data, 9)
        return pickle.dumps((os.path.basename(file_name), file_data))
