from os import path

from apps.core.task.gnrtaskstate import GNRTaskDefinition, AdvanceVerificationOptions


class RendererInfo:
    def __init__(self, name, defaults, task_builder_type, dialog, dialog_customizer, options):
        self.name = name
        self.output_formats = []
        self.scene_file_ext = []
        self.defaults = defaults
        self.task_builder_type = task_builder_type
        self.dialog = dialog
        self.dialog_customizer = dialog_customizer
        self.options = options


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
        self.options = None

        self.main_scene_file = ""

        self.output_format = ""
        self.task_name = ""

    def is_valid(self):
        is_valid, err = super(RenderingTaskDefinition, self).is_valid()
        if is_valid and not path.exists(self.main_scene_file):
            return False, u"Main scene file {} is not properly set".format(self.main_scene_file)
        return is_valid, err

class AdvanceRenderingVerificationOptions(AdvanceVerificationOptions):
    def __init__(self):
        AdvanceVerificationOptions.__init__(self)
        self.box_size = (5, 5)
        self.probability = 0.01
