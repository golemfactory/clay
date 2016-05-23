import unittest
import os

from gnr.benchmarks.luxrender.luxbenchmark import LuxBenchmark
from gnr.benchmarks.benchmark import Benchmark
from gnr.renderingtaskstate import RenderingTaskDefinition
from gnr.task.luxrendertask import LuxRenderOptions

from gnr.renderingdirmanager import get_benchmarks_path

class TestLuxBenchmark(unittest.TestCase):
    def setUp(self):
        self.lb = LuxBenchmark()
        self.task_path = os.path.join(get_benchmarks_path(), "luxrender", "lux_task")
    
    def test_is_instance(self):
        self.assertIsInstance(self.lb, LuxBenchmark)
        self.assertIsInstance(self.lb, Benchmark)
        self.assertIsInstance(self.lb.task_definition, RenderingTaskDefinition)
        self.assertIsInstance(self.lb.task_definition.renderer_options, LuxRenderOptions)
    
    def test_task_settings(self):
        self.assertTrue(self.lb.normalization_constant == 9910)
        self.assertTrue(self.lb.lux_task_path == self.task_path)
        self.assertTrue(self.lb.task_definition.output_file == "/tmp/lux_benchmark.png")
        self.assertTrue(self.lb.task_definition.tasktype == "LuxRender")
        self.assertTrue(self.lb.task_definition.renderer == "LuxRender")
        self.assertTrue(self.lb.task_definition.output_format == "png")
        self.assertTrue(self.lb.task_definition.task_id == u"{}".format("lux_benchmark"))
        self.assertTrue(os.path.isfile(self.lb.task_definition.main_scene_file))
        self.assertTrue(os.path.isfile(self.lb.task_definition.main_program_file))
        
        