import shutil
import os
import zlib
import cPickle as pickle

from mock import Mock

from golem.resource.dirmanager import DirManager
from golem.task.taskbase import result_types
from golem.task.taskstate import SubtaskStatus
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

    def test_interpret_task_results(self):
        task = self._get_gnr_task()

        files = self.additional_dir_content([5])
        shutil.move(files[2], files[2]+".log")
        files[2] += ".log"
        shutil.move(files[3], files[3]+"err.log")
        files[3] += "err.log"
        subtask_id = "xxyyzz"
        task.interpret_task_results(subtask_id, files, result_types["files"])
        files[2] = os.path.join(self.path, "xxyyzz" + os.path.basename(files[2]))
        files[3] = os.path.join(self.path, "xxyyzz" + os.path.basename(files[3]))
        self.assertEqual(task.results[subtask_id], [files[0], files[1], files[4]])
        self.assertEqual(task.stderr[subtask_id], files[3])
        self.assertEqual(task.stdout[subtask_id], files[2])

        for f in files:
            os.remove(f)
            self.assertFalse(os.path.isfile(f))

        res = [self.__compress_and_pickle_file(files[0], "abc"*1000),
               self.__compress_and_pickle_file(files[1], "def"*100),
               self.__compress_and_pickle_file(files[2], "outputlog"),
               self.__compress_and_pickle_file(files[3], "errlog"),
               self.__compress_and_pickle_file(files[4], "ghi")]
        subtask_id = "aabbcc"
        task.interpret_task_results(subtask_id, res, result_types["data"])
        files[2] = os.path.join(self.path, "aabbcc" + os.path.basename(files[2]))
        files[3] = os.path.join(self.path, "aabbcc" + os.path.basename(files[3]))

        self.assertEqual(task.results[subtask_id], [os.path.join(task.tmp_dir, os.path.basename(files[0])),
                                                    os.path.join(task.tmp_dir, os.path.basename(files[1])),
                                                    os.path.join(task.tmp_dir, os.path.basename(files[4]))])
        self.assertEqual(task.stderr[subtask_id], os.path.join(task.tmp_dir, os.path.basename(files[3])))
        self.assertEqual(task.stdout[subtask_id], os.path.join(task.tmp_dir, os.path.basename(files[2])))
        for f in files:
            self.assertTrue(os.path.isfile(os.path.join(task.tmp_dir, os.path.basename(f))))
        subtask_id = "112233"
        task.interpret_task_results(subtask_id, res, 58)
        self.assertEqual(task.results[subtask_id], [])
        self.assertEqual(task.stderr[subtask_id], "[GOLEM] Task result 58 not supported")
        self.assertEqual(task.stdout[subtask_id], "")

    def __compress_and_pickle_file(self, file_name, data):
        file_data = zlib.compress(data, 9)
        return pickle.dumps((os.path.basename(file_name), file_data))

    def test_verify(self):
        task = self._get_gnr_task()
        with self.assertLogs(logger, level="WARNING"):
            task.verify_subtask("abc")
        task.subtasks_given["abc"] = {'status': SubtaskStatus.starting, 'verified': False}
        assert task.should_accept("abc")
        task.subtasks_given["abc"] = {'status': SubtaskStatus.restarted, 'verified': False}
        assert not task.should_accept("abc")
        assert task.should_verify("abc")
        assert task.verify_results("abc", [],  0) == []
        assert task.subtasks_given["abc"]["verified"] == False
        files_ = self.additional_dir_content([3])
        assert task.verify_results("abc", files_, 1) == files_
        assert task.subtasks_given["abc"]["verified"] == True
        task.subtasks_given["abc"] = {'status': SubtaskStatus.restarted, 'verified': False}
        task.computation_finished("abc", files_,  1)
        assert task.subtasks_given["abc"]["verified"] == True
