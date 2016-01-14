from gnr.task.pbrtgnrtask import PbrtGNRTaskBuilder, build_pbrt_renderer_info, PbrtRendererOptions
from gnr.task.vraytask import VRayTaskBuilder
from gnr.task.threedsmaxtask import ThreeDSMaxTaskBuilder
from gnr.task.pythongnrtask import PythonGNRTaskBuilder
from gnr.task.luxrendertask import LuxRenderTaskBuilder
from gnr.task.blenderrendertask import BlenderRenderTaskBuilder
from gnr.task.gnrtask import GNROptions
from gnr.ui.dialog import PbrtTaskDialog
from gnr.customizers.pbrttaskdialogcustomizer import PbrtTaskDialogCustomizer


def build_pbrt_task_type():
    renderer = build_pbrt_renderer_info()
    options = GNROptions()
    options.output_formats = renderer.output_formats
    options.scene_file_ext = renderer.scene_file_ext
    options.defaults = renderer.defaults
    renderer_options = PbrtRendererOptions()
    options.filters = renderer_options.filters
    options.pixel_filter = renderer_options.pixel_filter
    options.path_tracers = renderer_options.path_tracers
    options.algorithm_type = renderer_options.algorithm_type
    options.samples_per_pixel_count = renderer_options.samples_per_pixel_count
    options.resolution = renderer.defaults.resolution
    options.output_format = renderer.defaults.output_format
    options.main_program_file = renderer.defaults.main_program_file
    options.full_task_timeout = renderer.defaults.full_task_timeout
    options.min_subtask_time = renderer.defaults.min_subtask_time
    options.min_subtasks = renderer.defaults.min_subtasks
    options.max_subtasks = renderer.defaults.max_subtasks
    options.default_subtasks = renderer.defaults.default_subtasks
    options.main_scene_file = ''
    options.output_file = ''
    options.verification_options = None

    return TaskType("PBRT", PbrtGNRTaskBuilder, options, PbrtTaskDialog, PbrtTaskDialogCustomizer)


def build_3ds_max_task_type():
    return TaskType("3ds Max Renderer", ThreeDSMaxTaskBuilder)


def build_vray_task_type():
    return TaskType("VRay Standalone", VRayTaskBuilder)


def build_luxrender_task_type():
    return TaskType("LuxRender", LuxRenderTaskBuilder)


def build_blender_render_task_type():
    return TaskType("BlenderRender", BlenderRenderTaskBuilder)


def build_python_gnr_task_type():
    return TaskType("Python GNR Task", PythonGNRTaskBuilder)


class TaskType:
    def __init__(self, name, task_builder_type, options=None, dialog=None, dialog_customizer=None):
        self.name = name
        self.task_builder_type = task_builder_type
        self.options = options
        self.dialog = dialog
        self.dialog_customizer = dialog_customizer
