import os
import tempfile

from apps.core.benchmark.benchmark import Benchmark
from apps.blender.task.blenderrendertask import BlenderRendererOptions
from gnr.renderingdirmanager import find_task_script


class BlenderBenchmark(Benchmark):
    def __init__(self):
        
        Benchmark.__init__(self)
        
        self.normalization_constant = 9360
        
        self.blender_task_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_task")
        
        self.task_definition.output_file = os.path.join(tempfile.gettempdir(), "blender_benchmark.png")
        self.task_definition.tasktype = "Blender"
        self.task_definition.renderer = "Blender"
        self.task_definition.output_format = "png"
        self.task_definition.renderer_options = BlenderRendererOptions()
        self.task_definition.renderer_options.frames = [1]
        
        self.task_definition.task_id = u"{}".format("blender_benchmark")
        self.task_definition.main_scene_file = os.path.join(self.blender_task_path, "scene-Helicopter-27-cycles.blend")
        self.task_definition.main_program_file = u"{}".format(find_task_script(__file__, "docker_blendertask.py"))

        self.task_definition.resources.add(os.path.normpath(self.task_definition.main_scene_file))
