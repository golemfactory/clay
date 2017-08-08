import os
import tempfile
import unittest

from apps.core.benchmark.benchmark import Benchmark
from apps.dummy.benchmark.benchmark import DummyBenchmark
from apps.dummy.task.dummytaskstate import DummyTaskDefinition, DummyTaskOptions


class TestDummyBenchmark(unittest.TestCase):
    def setUp(self):
        self.db = DummyBenchmark()

    def test_is_instance(self):
        self.assertIsInstance(self.db, DummyBenchmark)
        self.assertIsInstance(self.db.task_definition, DummyTaskDefinition)
        self.assertIsInstance(self.db.task_definition.options, DummyTaskOptions)

    def test_task_settings(self):
        self.assertTrue(os.path.isdir(self.db.dummy_task_path))

        self.assertTrue(self.db.task_definition.out_file_basename ==\
                        os.path.join(tempfile.gettempdir(), "out"))
        self.assertTrue(self.db.task_definition.task_id == u"{}".format("dummy_benchmark"))

        self.assertTrue(all(os.path.isfile(x) for x in self.db.task_definition.shared_data_files))
        self.assertTrue(os.path.isfile(self.db.task_definition.main_program_file))

        self.assertTrue(self.db.task_definition.difficulty == 0x00ffffff)
        self.assertTrue(self.db.task_definition.result_size == 256)
        self.assertTrue(self.db.task_definition.subtask_data_size == 2048)
        self.assertTrue(self.db.task_definition.shared_data_size == 36)
        sizes = sum(os.stat(x).st_size for x in self.db.task_definition.shared_data_files)
        self.assertTrue(sizes, self.db.task_definition.shared_data_size)