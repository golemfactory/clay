import cPickle as pickle
import shutil
import os
import zlib
from copy import copy

from mock import MagicMock

from golem.core.fileshelper import outer_dir_path
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import result_types, TaskEventListener
from golem.task.taskstate import SubtaskStatus
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture

from apps.core.task.gnrtask import GNRTask, logger


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

        task.subtasks_given[subtask_id] = {}
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

        assert len(task.listeners) == 0
        class TestListener(TaskEventListener):
            def __init__(self):
                super(TestListener, self).__init__()
                self.notify_called = False
                self.task_id = None

            def notify_update_task(self, task_id):
                self.notify_called = True
                self.task_id = task_id

        l1 = TestListener()
        l2 = TestListener()
        l3 = TestListener()
        task.register_listener(l1)
        task.register_listener(l2)
        task.register_listener(l3)
        task.unregister_listener(l2)
        task.notify_update_task()
        assert not l2.notify_called
        assert l1.notify_called
        assert l3.notify_called
        assert l1.task_id == "xyz"
        assert l3.task_id == "xyz"
        assert l2.task_id is None

    def test_interpret_task_results(self):
        task = self._get_gnr_task()

        subtask_id = "xxyyzz"
        files_dir = os.path.join(task.tmp_dir, subtask_id)
        files = self.additional_dir_content([5], sub_dir=files_dir)

        shutil.move(files[2], files[2]+".log")
        files[2] += ".log"
        shutil.move(files[3], files[3]+"err.log")
        files[3] += "err.log"

        files_copy = copy(files)

        task.interpret_task_results(subtask_id, files, result_types["files"])

        files[0] = outer_dir_path(files[0])
        files[1] = outer_dir_path(files[1])
        files[4] = outer_dir_path(files[4])

        self.assertEqual(task.results[subtask_id], [files[0], files[1], files[4]])
        self.assertEqual(task.stderr[subtask_id], files[3])
        self.assertEqual(task.stdout[subtask_id], files[2])

        for f in files_copy:
            with open(f, 'w'):
                pass

        task.interpret_task_results(subtask_id, files_copy, result_types["files"])
        self.assertEqual(task.results[subtask_id], [files[0], files[1], files[4]])
        for f in files_copy:
            with open(f, 'w'):
                pass
        os.remove(files[0])
        os.makedirs(files[0])
        with self.assertLogs(logger, level="WARNING"):
            task.interpret_task_results(subtask_id, files_copy, result_types["files"])
        assert task.results[subtask_id] == [files[1], files[4]]

        os.removedirs(files[0])

        for f in files + files_copy:
            if os.path.isfile(f):
                os.remove(f)
            assert not os.path.isfile(f)

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

    def test_restart(self):
        task = self._get_gnr_task()
        task.num_tasks_received = 1
        task.last_task = 8
        task.num_failed_subtasks = 2
        task.counting_nodes = MagicMock()

        task.subtasks_given["xyz"] = {'status': SubtaskStatus.finished, 'start_task': 1, 'end_task': 1, 'node_id': 'ABC'}
        task.subtasks_given["abc"] = {'status': SubtaskStatus.failure, 'start_task': 4, 'end_task': 4, 'node_id': 'abc'}
        task.subtasks_given["def"] = {'status': SubtaskStatus.starting, 'start_task': 8, 'end_task': 8, 'node_id': 'DEF'}
        task.subtasks_given["ghi"] = {'status': SubtaskStatus.resent, 'start_task': 2, 'end_task': 2, 'node_id': 'aha'}
        task.restart()
        assert task.num_tasks_received == 0
        assert task.last_task == 8
        assert task.num_failed_subtasks == 4
        assert task.subtasks_given["xyz"]["status"] == SubtaskStatus.restarted
        assert task.subtasks_given["abc"]["status"] == SubtaskStatus.failure
        assert task.subtasks_given["def"]["status"] == SubtaskStatus.restarted
        assert task.subtasks_given["ghi"]["status"] == SubtaskStatus.resent

    def __compress_and_pickle_file(self, file_name, data):
        file_data = zlib.compress(data, 9)
        return pickle.dumps((os.path.basename(file_name), file_data))

