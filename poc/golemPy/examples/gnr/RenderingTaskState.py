from golem.task.TaskState import TaskState

from examples.gnr.GNRTaskState import GNRTaskDefinition, AdvanceVerificationOptions

###########################################################################
class RendererInfo:
    #########################
    def __init__(self, name, defaults, task_builderType, dialog, dialogCustomizer, rendererOptions):
        self.name           = name
        self.outputFormats  = []
        self.scene_fileExt   = []
        self.defaults       = defaults
        self.task_builderType = task_builderType
        self.dialog = dialog
        self.dialogCustomizer = dialogCustomizer
        self.rendererOptions = rendererOptions

###########################################################################
class RendererDefaults:
    #########################
    def __init__(self):
        self.outputFormat       = ""
        self.mainProgramFile    = ""
        self.full_task_timeout    = 4 * 3600
        self.min_subtask_time     = 60
        self.subtask_timeout     = 20 * 60
        self.resolution         = [800, 600]
        self.minSubtasks        = 1
        self.maxSubtasks        = 50
        self.defaultSubtasks    = 20

###########################################################################
class RenderingTaskDefinition(GNRTaskDefinition):
    #########################
    def __init__(self):
        GNRTaskDefinition.__init__(self)

        self.resolution         = [ 0, 0 ]
        self.renderer           = None
        self.rendererOptions    = None

        self.mainSceneFile      = ""
        self.output_file         = ""
        self.outputFormat       = ""

###########################################################################
class RenderingTaskState:
    #########################
    def __init__(self):
        self.definition     = RenderingTaskDefinition()
        self.task_state      = TaskState()

###########################################################################
class AdvanceRenderingVerificationOptions (AdvanceVerificationOptions):
    def __init__(self):
        AdvanceVerificationOptions.__init__(self)
        self.boxSize = (5, 5)
        self.probability = 0.01

