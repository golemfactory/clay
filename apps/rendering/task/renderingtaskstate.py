from golem.task.taskstate import TaskState
from gnr.gnrtaskstate import GNRTaskDefinition, AdvanceVerificationOptions


class RendererInfo:
    def __init__(self, name, defaults, task_builder_type, dialog, dialog_customizer, renderer_options):
        self.name = name
        self.output_formats = []
        self.scene_file_ext = []
        self.defaults = defaults
        self.task_builder_type = task_builder_type
        self.dialog = dialog
        self.dialog_customizer = dialog_customizer
        self.renderer_options = renderer_options


class RendererDefaults:
    def __init__(self):
        self.output_format = ""
        self.main_program_file = ""
        self.full_task_timeout = 4 * 3600
        self.subtask_timeout = 20 * 60
        self.resolution = [800, 600]
        self.min_subtasks = 1
        self.max_subtasks = 50
        self.default_subtasks = 20
        self.task_name = ""


class RenderingTaskDefinition(GNRTaskDefinition):
    def __init__(self):
        GNRTaskDefinition.__init__(self)

        self.resolution = [0, 0]
        self.renderer = None
        self.renderer_options = None

        self.main_scene_file = ""
        self.output_file = ""
        self.output_format = ""
        self.task_name = ""


class RenderingTaskState:
    def __init__(self):
        self.definition = RenderingTaskDefinition()
        self.task_state = TaskState()


class AdvanceRenderingVerificationOptions(AdvanceVerificationOptions):
    def __init__(self):
        AdvanceVerificationOptions.__init__(self)
        self.box_size = (5, 5)
        self.probability = 0.01
