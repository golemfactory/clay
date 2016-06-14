import shutil
import os
import zlib
import cPickle as pickle

from mock import Mock

from gnr.task.gnrtask import GNRTask, logger
from golem.task.taskbase import result_types
from golem.task.taskstate import SubtaskStatus
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture


class TestGNRTask(LogTestCase, TestDirFixture):
    def _get_gnr_task(self):
        return GNRTask("src code", "ABC", "xyz", "10.10.10.10", 123, "key",
                        "environment", 3000, 30, 1024, 1024, 100)

    def test_gnr_task(self):
        task = self._get_gnr_task()
        self.assertIsInstance(task, GNRTask)
        self.assertEqual(task.header.max_price, 100)

        subtask_id = "xxyyzz"
        self.assertEqual(task.get_stdout(subtask_id), "")
        self.assertEqual(task.get_stderr(subtask_id), "")
        self.assertEqual(task.get_results(subtask_id), [])

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

        self.assertEqual(task.get_stdout(subtask_id), "stdout in file")
        self.assertEqual(task.get_stderr(subtask_id), "stderr in file")

    def test_interpret_task_results(self):
        task = self._get_gnr_task()

        files = self.additional_dir_content([5])
        shutil.move(files[2], files[2]+".log")
        files[2] += ".log"
        shutil.move(files[3], files[3]+".err.log")
        files[3] += ".err.log"
        subtask_id = "xxyyzz"
        task.interpret_task_results(subtask_id, files, result_types["files"], self.path)
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
        task.interpret_task_results(subtask_id, res, result_types["data"], self.path)
        self.assertEqual(task.results[subtask_id], [files[0], files[1], files[4]])
        self.assertEqual(task.stderr[subtask_id], files[3])
        self.assertEqual(task.stdout[subtask_id], files[2])
        for f in files:
            self.assertTrue(os.path.isfile(f))
        subtask_id = "112233"
        task.interpret_task_results(subtask_id, res, 58, self.path)
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
        dir_manager = Mock()
        dir_manager.get_task_temporary_dir.return_value = self.path
        assert task.verify_results("abc", [], dir_manager, 0) == []
        assert task.subtasks_given["abc"]["verified"] == False
        files_ = self.additional_dir_content([3])
        assert task.verify_results("abc", files_, dir_manager, 1) == files_
        assert task.subtasks_given["abc"]["verified"] == True
        task.subtasks_given["abc"] = {'status': SubtaskStatus.restarted, 'verified': False}
        task.computation_finished("abc", files_, dir_manager, 1)
        assert task.subtasks_given["abc"]["verified"] == True










