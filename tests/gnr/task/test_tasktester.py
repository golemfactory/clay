import os
import shutil
from mock import Mock

from gnr.task.tasktester import TaskTester
from golem.tools.testdirfixture import TestDirFixture
from golem.task.taskbase import Task
from gnr.renderingdirmanager import get_tmp_path

def callback(a, b):
    return

class TaskThread:
    def __init__(self, result):
        self.result = result

class TestTaskTester(TestDirFixture):
    
    task = Task(Mock(), Mock())
    node = 'node1'
    task_name = 'task1'
    
    def testInit(self):
        self.assertIsNotNone(TaskTester(self.task, self.path, None))
        
    def testTaskComputed(self):
        result = [{"data":True}, 123]
        file1 = os.path.join(self.path, 'file1.flm')
        
        open(file1, 'w').close()
        
        self.assertTrue(os.path.isfile(file1))
        
        self.task.header.node_name = self.node
        self.task.header.task_id = self.task_name
        self.task.root_path = self.path
        
        tt = TaskTester(self.task, self.path, callback)
        tt.tmp_dir = self.path
        task_thread = TaskThread(result)
        tt.task_computed(task_thread)
        
        copied_filepath = os.path.join(get_tmp_path(self.node, self.task_name, self.path), "test_result.flm")
        self.assertTrue(os.path.isfile(copied_filepath))