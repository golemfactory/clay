import pathlib
import sys
import tempfile
from typing import Type

from os.path import dirname, join, realpath
from os import close

from apps.blender.blenderenvironment import BlenderEnvironment, \
    BlenderNVGPUEnvironment
from apps.blender.task.blenderrendertask import BlenderRendererOptions, \
    BlenderNVGPURendererOptions
from apps.rendering.benchmark.renderingbenchmark import RenderingBenchmark


class BlenderBenchmark(RenderingBenchmark):
    RENDERER_OPTIONS_CLASS = BlenderRendererOptions
    ENVIRONMENT_CLASS: Type[BlenderEnvironment] = BlenderEnvironment
    SCENE_FILE_NAME: str = "bmw27_cpu.blend"

    def __init__(self):
        super(BlenderBenchmark, self).__init__()
        self._normalization_constant = 9360
        if hasattr(sys, 'frozen') and sys.frozen:
            real_exe_path = realpath(sys.executable)
            self.blender_task_path = join(dirname(real_exe_path),
                                          'examples', 'blender')
        else:
            this_dir = pathlib.Path(__file__).resolve().parent
            self.blender_task_path = str(this_dir / "test_task")
        task_def = self.task_definition
        handle, task_def.output_file = tempfile.mkstemp("blender_benchmark.png")
        close(handle)
        task_def.task_type = "Blender"
        task_def.output_format = "png"
        task_def.options = self.RENDERER_OPTIONS_CLASS()
        task_def.options.frames = "1"
        main_scene_file = pathlib.Path(self.blender_task_path)
        main_scene_file /= self.SCENE_FILE_NAME
        task_def.main_scene_file = str(main_scene_file)
        task_def.resources.add(str(main_scene_file.resolve()))


class BlenderNVGPUBenchmark(BlenderBenchmark):
    RENDERER_OPTIONS_CLASS = BlenderNVGPURendererOptions
    ENVIRONMENT_CLASS: Type[BlenderEnvironment] = BlenderNVGPUEnvironment
    SCENE_FILE_NAME: str = "bmw27_gpu.blend"
