import os
import tempfile
import unittest

from apps.core.benchmark.benchmark import Benchmark
from apps.lux.benchmark.benchmark import LuxBenchmark
from apps.lux.task.luxrendertask import LuxRenderOptions
from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition


class TestLuxBenchmark(unittest.TestCase):
    def setUp(self):
        self.lb = LuxBenchmark()

    def test_is_instance(self):
        self.assertIsInstance(self.lb, LuxBenchmark)
        self.assertIsInstance(self.lb, Benchmark)
        self.assertIsInstance(self.lb.task_definition, RenderingTaskDefinition)
        self.assertIsInstance(self.lb.task_definition.options, LuxRenderOptions)
    
    def test_task_settings(self):
        self.assertTrue(self.lb.normalization_constant == 9910)
        self.assertTrue(os.path.isdir(self.lb.lux_task_path))
        self.assertTrue(self.lb.task_definition.output_file == os.path.join(tempfile.gettempdir(), "lux_benchmark.png"))
        self.assertTrue(self.lb.task_definition.task_type == "LuxRender")
        self.assertTrue(self.lb.task_definition.output_format == "png")
        self.assertTrue(self.lb.task_definition.task_id == u"{}".format("lux_benchmark"))
        self.assertTrue(os.path.isfile(self.lb.task_definition.main_scene_file))
        self.assertTrue(os.path.isfile(self.lb.task_definition.main_program_file))
