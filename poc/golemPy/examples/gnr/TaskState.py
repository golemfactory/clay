from PyQt4 import QtCore
from golem.task.TaskState import TaskState

class RendererInfo:
    #########################
    def __init__( self, name, defaults, taskBuilderType, dialog, dialogCustomizer, rendererOptions):
        self.name           = name
        self.outputFormats  = []
        self.sceneFileExt   = []
        self.defaults       = defaults
        self.taskBuilderType = taskBuilderType
        self.dialog = dialog
        self.dialogCustomizer = dialogCustomizer
        self.options = rendererOptions

class RendererDefaults:
    #########################
    def __init__( self ):
        self.outputFormat       = ""
        self.mainProgramFile    = ""
        self.fullTaskTimeout    = 4 * 3600
        self.minSubtaskTime     = 60
        self.subtaskTimeout     = 20 * 60
        self.resolution         = [800, 600]
        self.minSubtasks        = 1
        self.maxSubtasks        = 50
        self.defaultSubtasks    = 20

class TestTaskInfo:
    #########################
    def __init__( self, name ):
        self.name           = name
        # TODO

class TaskDefinition:
    #########################
    def __init__( self ):
        self.taskId                 = ""
        self.fullTaskTimeout    = 0
        self.subtaskTimeout     = 0
        self.minSubtaskTime     = 0

        self.resolution         = [ 0, 0 ]
        self.renderer           = None

        self.resources          = set()
        self.rendererOptions    = None

        self.mainProgramFile    = ""
        self.mainSceneFile      = ""
        self.outputFile         = ""
        self.outputFormat       = ""

        self.estimatedMemory    = 0

        self.totalSubtasks      = 0
        self.optimizeTotal      = False

class GNRTaskState:
    #########################
    def __init__( self ):
        self.definition     = TaskDefinition()
        self.taskState      = TaskState()
