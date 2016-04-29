import logging

import os

from gnr.benchmarks.benchmark import Benchmark
from gnr.renderingdirmanager import get_benchmarks_path, find_task_script
from gnr.task.blenderrendertask import BlenderRendererOptions
from gnr.renderingtaskstate import RenderingTaskDefinition

logger = logging.getLogger(__name__)

class BlenderBenchmark(Benchmark):
    def __init__(self):
        
        Benchmark.__init__(self)
        
        self.blender_task_path = os.path.join(get_benchmarks_path(), "blender", "blender_task")
        
        self.task_definition.output_file = "/tmp/lux_benchmark.png"
        self.task_definition.tasktype = "Blender"
        self.task_definition.renderer = "Blender"
        self.task_definition.output_format = "png"
        self.task_definition.renderer_options = BlenderRendererOptions()
        self.task_definition.renderer_options.frames = [1]
        self.task_definition.renderer_options.default_subtasks = 1
        self.task_definition.total_tasks = 1
        self.task_definition.start_task = 1
        self.task_definition.end_task = 1
        
        self.task_definition.task_id = u"{}".format("blender_benchmark")
        self.task_definition.main_scene_file = os.path.join(self.blender_task_path, "scene-Helicopter-27-cycles.blend")
        self.task_definition.main_program_file = u"{}".format(find_task_script("docker_blendertask.py"))
        

        self.task_definition.resources.add(os.path.normpath(self.task_definition.main_scene_file))

    
