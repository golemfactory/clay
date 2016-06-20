import shutil
import os
import zlib
import cPickle as pickle
from datetime import datetime, timedelta

from mock import Mock

from gnr.task.gnrtask import GNRTask, logger
from golem.task.taskbase import result_types
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture


class TestGNRTask(LogTestCase, TestDirFixture):
    def test_gnr_task(self):
        task = GNRTask("src code", "ABC", "xyz", "10.10.10.10", 123, "key",
                       "environment", 3000, 30, 1024, 1024, 100)
        self.assertIsInstance(task, GNRTask)
        self.assertEqual(task.header.max_price, 100)

        subtask_id = "xxyyzz"
        with self.assertLogs(logger, level=0) as l:
            self.assertEqual(task.get_stdout(subtask_id), False)
        self.assertTrue(any(["not my subtask" in log for log in l.output]))
        with self.assertLogs(logger, level=0) as l:
            self.assertEqual(task.get_stderr(subtask_id), False)
        self.assertTrue(any(["not my subtask" in log for log in l.output]))
        with self.assertLogs(logger, level=0) as l:
            self.assertEqual(task.get_results(subtask_id), False)
        self.assertTrue(any(["not my subtask" in log for log in l.output]))

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

        task.restart()
        assert task.num_tasks_received == 0
        assert task.last_task == 0
        assert len(task.subtasks_given) == 0
        assert task.num_failed_subtasks == 0
        assert task.header.deadline >= datetime.utcnow() + timedelta(seconds=(task.full_task_timeout - 2))

    def test_interpret_task_results(self):
        task = GNRTask("src code", "ABC", "xyz", "10.10.10.10", 123, "key",
                       "environment", 3000, 30, 1024, 1024, 100)

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






