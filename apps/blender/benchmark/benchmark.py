import pathlib
import tempfile

from apps.core.benchmark.benchmark import Benchmark
from apps.blender.task.blenderrendertask import BlenderRendererOptions
from apps.blender.blenderenvironment import BlenderEnvironment


class BlenderBenchmark(Benchmark):
    def __init__(self):
        super(BlenderBenchmark, self).__init__()
        self.normalization_constant = 9360
        this_dir = pathlib.Path(__file__).resolve().parent
        self.blender_task_path = str(this_dir / "test_task")
        task_def = self.task_definition
        task_def.output_file = tempfile.mkstemp("blender_benchmark.png")[1]
        task_def.task_type = "Blender"
        task_def.output_format = "png"
        task_def.options = BlenderRendererOptions()
        task_def.options.frames = "1"
        task_def.task_id = u"blender_benchmark"
        main_scene_file = pathlib.Path(self.blender_task_path)
        main_scene_file /= "bmw27_cpu.blend"
        task_def.main_scene_file = str(main_scene_file)
        task_def.main_program_file = BlenderEnvironment().main_program_file
        task_def.resources.add(str(main_scene_file.resolve()))
