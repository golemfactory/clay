import os
import tempfile
import unittest

from apps.dummy.benchmark.benchmark import DummyTaskBenchmark
from apps.dummy.task.dummytaskstate import DummyTaskDefinition, DummyTaskOptions


class TestDummyBenchmark(unittest.TestCase):
    def setUp(self):
        self.db = DummyTaskBenchmark()

    def test_is_instance(self):
        self.assertIsInstance(self.db, DummyTaskBenchmark)
        self.assertIsInstance(self.db.task_definition, DummyTaskDefinition)
        self.assertIsInstance(self.db.task_definition.options, DummyTaskOptions)

    def test_task_settings(self):
        self.assertTrue(os.path.isdir(self.db.dummy_task_path))

        self.assertTrue(self.db.task_definition.out_file_basename == "out")
        self.assertTrue(self.db.task_definition.task_id == u"{}".format("dummy_benchmark"))

        self.assertTrue(all(os.path.isfile(x) for x in self.db.task_definition.shared_data_files))
        self.assertTrue(os.path.isfile(self.db.task_definition.main_program_file))

        self.assertTrue(self.db.task_definition.options.difficulty == 0xffff0000)
        self.assertTrue(self.db.task_definition.result_size == 256)
        self.assertTrue(self.db.task_definition.options.subtask_data_size == 128)
        sizes = sum(os.stat(x).st_size for x in self.db.task_definition.shared_data_files)
