from golem.task.TaskState import TaskState

from examples.gnr.GNRTaskState import GNRTaskDefinition, AdvanceVerificationOptions

###########################################################################
class RendererInfo:
    #########################
    def __init__(self, name, defaults, taskBuilderType, dialog, dialogCustomizer, rendererOptions):
        self.name           = name
        self.outputFormats  = []
        self.sceneFileExt   = []
        self.defaults       = defaults
        self.taskBuilderType = taskBuilderType
        self.dialog = dialog
        self.dialogCustomizer = dialogCustomizer
        self.rendererOptions = rendererOptions

###########################################################################
class RendererDefaults:
    #########################
    def __init__(self):
        self.outputFormat       = ""
        self.mainProgramFile    = ""
        self.fullTaskTimeout    = 4 * 3600
        self.minSubtaskTime     = 60
        self.subtaskTimeout     = 20 * 60
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
        self.outputFile         = ""
        self.outputFormat       = ""

###########################################################################
class RenderingTaskState:
    #########################
    def __init__(self):
        self.definition     = RenderingTaskDefinition()
        self.taskState      = TaskState()

###########################################################################
class AdvanceRenderingVerificationOptions (AdvanceVerificationOptions):
    def __init__(self):
        AdvanceVerificationOptions.__init__(self)
        self.boxSize = (5, 5)
        self.probability = 0.01

