from PyQt4 import QtCore
from golem.task.TaskState import TaskState

class TaskComputerInfo:
    #########################
    def __init__( self ):
        self.id             = ""
        self.subtaskId      = 0
        self.status         = ""
        self.progress       = 0.0
        self.ip             = ""
        self.power          = 0
        self.subtaskDef     = ""

class RendererInfo:
    #########################
    def __init__( self, name, defaults, taskBuilderType, dialog, dialogCustomizer, rendererOptions):
        self.name           = name
        self.filters        = []
        self.pathTracers    = []
        self.outputFormats  = []
        self.sceneFileExt   = "pbrt"
        self.defaults       = defaults
        self.taskBuilderType = taskBuilderType
        self.dialog = dialog
        self.dialogCustomizer = dialogCustomizer
        self.rendererOptions = rendererOptions

class RendererDefaults:
    #########################
    def __init__( self ):
        self.samplesPerPixel    = 0
        self.outputFormat       = ""
        self.mainProgramFile    = ""
        self.fullTaskTimeout    = 0
        self.minSubtaskTime     = 0
        self.subtaskTimeout     = 0
        self.outputResX         = 800
        self.outputResY         = 600

class TestTaskInfo:
    #########################
    def __init__( self, name ):
        self.name           = name
        # TODO

class TaskDefinition:
    #########################
    def __init__( self ):
        self.id                 = ""
        self.minPower           = 0
        self.minSubtask         = 0
        self.maxSubtask         = 0
        self.subtaskTimeout     = 0
        self.minSubtaskTime     = 0
        self.resolution         = [ 0, 0 ]
        self.renderer           = None
        self.outputFile         = ""
        self.taskResources      = []
        self.fullTaskTimeout    = 0    
        self.mainProgramFile    = ""
        self.mainSceneFile      = ""
        self.outputFormat       = ""
        self.resources          = []
        self.estimatedMemory    = 0
        self.renderOptions = None

class GNRTaskState:
    #########################
    def __init__( self ):
        self.definition     = TaskDefinition()
        self.taskState      = TaskState()
