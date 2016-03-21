import os
from mock import Mock

from gnr.task.tasktester import TaskTester, logger
from golem.tools.testdirfixture import TestDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.task.taskbase import Task
from gnr.renderingdirmanager import get_tmp_path


class TaskThread:
    def __init__(self, result):
        self.result = result


class MemTaskThread(TaskThread):
    def __init__(self, result, memory, error):
        TaskThread.__init__(self, (result, memory))
        self.error_msg = error
        self.error = False

    def get_error(self):
        return self.error

    def get_progress(self):
        return "30%"


class TestTaskTester(TestDirFixture, LogTestCase):
    
    task = Task(Mock(), Mock())
    node = 'node1'
    task_name = 'task1'
    
    def test_init(self):
        self.assertIsNotNone(TaskTester(self.task, self.path, None))
        
    def test_task_computed(self):
        result = [{"data": True}, 123]
        file1 = os.path.join(self.path, 'file1.flm')
        
        open(file1, 'w').close()
        
        self.assertTrue(os.path.isfile(file1))
        
        self.task.header.node_name = self.node
        self.task.header.task_id = self.task_name
        self.task.root_path = self.path
        
        tt = TaskTester(self.task, self.path, Mock())
        tt.tmp_dir = self.path
        task_thread = TaskThread(result)
        tt.task_computed(task_thread)
        
        copied_filepath = os.path.join(get_tmp_path(self.node, self.task_name, self.path), "test_result.flm")
        self.assertTrue(os.path.isfile(copied_filepath))

        task_thread = MemTaskThread(None, 30210, "Some error")
        with self.assertLogs(logger, level=1):
            tt.task_computed(task_thread)
        tt.finished_callback.assert_called_with(False, error="Some error")

        task_thread = MemTaskThread("result", 2010, "Another error")
        self.assertIsNone(tt.get_progress())
        tt.tt = task_thread
        self.assertEqual(tt.get_progress(), "30%")
        task_thread.error = True
        self.assertEqual(tt.get_progress(), 0)
        tt.finished_callback.assert_called_with(False, error="Another error")







