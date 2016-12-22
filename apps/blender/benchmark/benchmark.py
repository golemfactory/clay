import os
import tempfile

from apps.core.benchmark.benchmark import Benchmark
from apps.blender.task.blenderrendertask import BlenderRendererOptions
from apps.rendering.task.renderingdirmanager import find_task_script

from golem.core.common import get_golem_path

APP_DIR = os.path.join(get_golem_path(), 'apps', 'blender')


class BlenderBenchmark(Benchmark):
    def __init__(self):
        
        Benchmark.__init__(self)
        
        self.normalization_constant = 9360
        
        self.blender_task_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_task")
        
        self.task_definition.output_file = os.path.join(tempfile.gettempdir(), "blender_benchmark.png")
        self.task_definition.task_type = "Blender"
        self.task_definition.output_format = "png"
        self.task_definition.options = BlenderRendererOptions()
        self.task_definition.options.frames = [1]
        self.task_definition.task_id = u"{}".format("blender_benchmark")
        self.task_definition.main_scene_file = os.path.join(self.blender_task_path, "scene-Helicopter-27-cycles.blend")
        self.task_definition.main_program_file = u"{}".format(find_task_script(APP_DIR, "docker_blendertask.py"))

        self.task_definition.resources.add(os.path.normpath(self.task_definition.main_scene_file))
