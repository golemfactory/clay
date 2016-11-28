import os
import tempfile

from apps.core.benchmark.benchmark import Benchmark
from gnr.renderingdirmanager import get_benchmarks_path, find_task_script
from gnr.task.luxrendertask import LuxRenderOptions


class LuxBenchmark(Benchmark):
    def __init__(self):
        
        Benchmark.__init__(self)
        
        self.normalization_constant = 9910
        
        self.lux_task_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_task")
        
        self.task_definition.output_file = os.path.join(tempfile.gettempdir(), "lux_benchmark.png")
        self.task_definition.tasktype = "LuxRender"
        self.task_definition.renderer = "LuxRender"
        self.task_definition.output_format = "png"
        self.task_definition.renderer_options = LuxRenderOptions()
        self.task_definition.renderer_options.haltspp = 5
        self.task_definition.renderer_options.halttime = 0        
        self.task_definition.task_id = u"{}".format("lux_benchmark")
        self.task_definition.main_scene_file = os.path.join(self.lux_task_path, "schoolcorridor.lxs")
        self.task_definition.main_program_file = u"{}".format(find_task_script("docker_luxtask.py"))
        self.task_definition.resources = self.find_resources()

    def find_resources(self):
        selection = []
        for root, dirs, files in os.walk(self.lux_task_path):
            for name in files:
                selection.append(os.path.join(root, name))
        return set(selection)
