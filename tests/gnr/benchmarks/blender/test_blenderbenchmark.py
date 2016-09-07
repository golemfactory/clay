import os
import tempfile
import unittest

from gnr.benchmarks.blender.blenderbenchmark import BlenderBenchmark
from gnr.benchmarks.benchmark import Benchmark
from gnr.renderingtaskstate import RenderingTaskDefinition
from gnr.task.blenderrendertask import BlenderRendererOptions

from gnr.renderingdirmanager import get_benchmarks_path


class TestBlenderBenchmark(unittest.TestCase):
    def setUp(self):
        self.bb = BlenderBenchmark()
        self.task_path = os.path.join(get_benchmarks_path(), "blender", "blender_task")
    
    def test_is_instance(self):
        self.assertIsInstance(self.bb, BlenderBenchmark)
        self.assertIsInstance(self.bb, Benchmark)
        self.assertIsInstance(self.bb.task_definition, RenderingTaskDefinition)
        self.assertIsInstance(self.bb.task_definition.renderer_options, BlenderRendererOptions)
    
    def test_task_settings(self):
        self.assertTrue(self.bb.normalization_constant == 9360)
        self.assertTrue(self.bb.blender_task_path == self.task_path)
        self.assertTrue(self.bb.task_definition.output_file == os.path.join(tempfile.gettempdir(),
                                                                            "blender_benchmark.png"))
        self.assertTrue(self.bb.task_definition.tasktype == "Blender")
        self.assertTrue(self.bb.task_definition.renderer == "Blender")
        self.assertTrue(self.bb.task_definition.output_format == "png")
        self.assertTrue(self.bb.task_definition.task_id == u"{}".format("blender_benchmark"))
        self.assertTrue(os.path.isfile(self.bb.task_definition.main_scene_file))
        self.assertTrue(os.path.isfile(self.bb.task_definition.main_program_file))
