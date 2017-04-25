import os
import tempfile
import unittest

from apps.blender.benchmark.benchmark import BlenderBenchmark
from apps.blender.task.blenderrendertask import BlenderRendererOptions, BlenderRenderTaskBuilder
from apps.core.benchmark.benchmarkrunner import BenchmarkRunner
from apps.core.benchmark.benchmark import Benchmark
from apps.core.task.coretaskstate import TaskDesc
from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition

from golem.resource.dirmanager import DirManager
from golem.task.taskbase import Task
from golem.task.taskstate import TaskStatus
from golem.testutils import TempDirFixture
from golem.tools.ci import ci_skip


class TestBlenderBenchmark(unittest.TestCase):
    def setUp(self):
        self.bb = BlenderBenchmark()
    
    def test_is_instance(self):
        self.assertIsInstance(self.bb, BlenderBenchmark)
        self.assertIsInstance(self.bb, Benchmark)
        self.assertIsInstance(self.bb.task_definition, RenderingTaskDefinition)
        self.assertIsInstance(self.bb.task_definition.options, BlenderRendererOptions)
    
    def test_task_settings(self):
        self.assertTrue(self.bb.normalization_constant == 9360)
        self.assertTrue(os.path.isdir(self.bb.blender_task_path))
        self.assertTrue(self.bb.task_definition.output_file == os.path.join(tempfile.gettempdir(),
                                                                            "blender_benchmark.png"))
        self.assertTrue(self.bb.task_definition.task_type == "Blender")
        self.assertTrue(self.bb.task_definition.output_format == "png")
        self.assertTrue(self.bb.task_definition.task_id == u"{}".format("blender_benchmark"))
        self.assertTrue(os.path.isfile(self.bb.task_definition.main_scene_file))
        self.assertTrue(os.path.isfile(self.bb.task_definition.main_program_file))


@ci_skip
class TestBenchmarkRunner(TempDirFixture):

    def test_run(self):
        benchmark = BlenderBenchmark()
        task_definition = benchmark.task_definition

        task_state = TaskDesc()
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
        if self.br.tt:
            self.br.tt.join()

        assert result[0]
