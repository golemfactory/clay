import sys
import tempfile
from os import walk
from os.path import abspath, dirname, join

from apps.lux.luxenvironment import LuxRenderEnvironment
from apps.lux.task.luxrendertask import LuxRenderOptions
from apps.rendering.benchmark.renderingbenchmark import RenderingBenchmark
from golem.core.common import get_golem_path

APP_DIR = join(get_golem_path(), 'apps', 'lux')


class LuxBenchmark(RenderingBenchmark):
    def __init__(self):

        RenderingBenchmark.__init__(self)

        self._normalization_constant = 9910

        if hasattr(sys, 'frozen') and sys.frozen:
            self.lux_task_path = join(dirname(sys.executable),
                                      'examples', 'lux')
        else:
            self.lux_task_path = join(dirname(abspath(__file__)), "test_task")

        self.task_definition.output_file = join(tempfile.gettempdir(),
                                                "lux_benchmark.png")
        self.task_definition.task_type = "LuxRender"
        self.task_definition.output_format = "png"
        self.task_definition.options = LuxRenderOptions()
        self.task_definition.options.haltspp = 5
        self.task_definition.options.halttime = 0
        self.task_definition.main_scene_file = join(self.lux_task_path,
                                                    "schoolcorridor.lxs")
        self.task_definition.main_program_file =\
            LuxRenderEnvironment().main_program_file
        self.task_definition.resources = self.find_resources()

    def find_resources(self):
        selection = []
        for root, dirs, files in walk(self.lux_task_path):
            for name in files:
                selection.append(join(root, name))
        return set(selection)
