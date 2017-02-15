import os
import tempfile

from golem.core.common import get_golem_path
from golem.resource.dirmanager import find_task_script

from apps.core.benchmark.benchmark import Benchmark
from apps.lux.task.luxrendertask import LuxRenderOptions
from apps.lux.luxenvironment import LuxRenderEnvironment

APP_DIR = os.path.join(get_golem_path(), 'apps', 'lux')


class LuxBenchmark(Benchmark):
    def __init__(self):
        
        Benchmark.__init__(self)
        
        self.normalization_constant = 9910
        
        self.lux_task_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_task")
        
        self.task_definition.output_file = os.path.join(tempfile.gettempdir(), "lux_benchmark.png")
        self.task_definition.task_type = "LuxRender"
        self.task_definition.output_format = "png"
        self.task_definition.options = LuxRenderOptions()
        self.task_definition.options.haltspp = 5
        self.task_definition.options.halttime = 0
        self.task_definition.task_id = u"{}".format("lux_benchmark")
        self.task_definition.main_scene_file = os.path.join(self.lux_task_path, "schoolcorridor.lxs")
        self.task_definition.main_program_file = LuxRenderEnvironment().main_program_file
        self.task_definition.resources = self.find_resources()

    def find_resources(self):
        selection = []
        for root, dirs, files in os.walk(self.lux_task_path):
            for name in files:
                selection.append(os.path.join(root, name))
        return set(selection)
