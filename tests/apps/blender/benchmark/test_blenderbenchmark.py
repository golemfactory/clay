import os
import tempfile
import unittest

from apps.blender.benchmark.benchmark import BlenderBenchmark
from apps.blender.task.blenderrendertask import BlenderRendererOptions, BlenderRenderTaskBuilder
from apps.core.benchmark.benchmarkrunner import BenchmarkRunner
from apps.core.benchmark.benchmark import Benchmark
from gnr.renderingtaskstate import RenderingTaskDefinition, RenderingTaskState

from golem.resource.dirmanager import DirManager
from golem.task.taskbase import Task
from golem.task.taskstate import TaskStatus
from golem.testutils import TempDirFixture


class TestBlenderBenchmark(unittest.TestCase):
    def setUp(self):
        self.bb = BlenderBenchmark()
    
    def test_is_instance(self):
        self.assertIsInstance(self.bb, BlenderBenchmark)
        self.assertIsInstance(self.bb, Benchmark)
        self.assertIsInstance(self.bb.task_definition, RenderingTaskDefinition)
        self.assertIsInstance(self.bb.task_definition.renderer_options, BlenderRendererOptions)
    
    def test_task_settings(self):
        self.assertTrue(self.bb.normalization_constant == 9360)
        self.assertTrue(os.path.isdir(self.bb.blender_task_path))
        self.assertTrue(self.bb.task_definition.output_file == os.path.join(tempfile.gettempdir(),
                                                                            "blender_benchmark.png"))
        self.assertTrue(self.bb.task_definition.tasktype == "Blender")
        self.assertTrue(self.bb.task_definition.renderer == "Blender")
        self.assertTrue(self.bb.task_definition.output_format == "png")
        self.assertTrue(self.bb.task_definition.task_id == u"{}".format("blender_benchmark"))
        self.assertTrue(os.path.isfile(self.bb.task_definition.main_scene_file))
        self.assertTrue(os.path.isfile(self.bb.task_definition.main_program_file))


class TestBenchmarkRunner(TempDirFixture):

    def test_run(self):
        benchmark = BlenderBenchmark()
        task_definition = benchmark.query_benchmark_task_definition()

        task_state = RenderingTaskState()
        task_state.status = TaskStatus.notStarted
        task_state.definition = task_definition

        dir_manager = DirManager(self.path)
        task = Task.build_task(BlenderRenderTaskBuilder("node name", task_definition, self.path, dir_manager))

        result = [None]

        def success(*_):
            result[0] = True

        def error(*_):
            result[0] = False

        self.br = BenchmarkRunner(task, self.path, success, error, benchmark)
        self.br.run()

        assert result[0]
