from PyQt4 import QtCore

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
    def __init__( self, name, defaults, taskBuilderType ):
        self.name           = name
        self.filters        = []
        self.pathTracers    = []
        self.outputFormats  = []
        self.sceneFileExt   = "pbrt"
        self.defaults       = defaults
        self.taskBuilderType = taskBuilderType

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
        self.algorithmType      = ""
        self.pixelFilter        = ""
        self.samplesPerPixelCount = 0
        self.outputFile         = ""
        self.taskResources      = []
        self.fullTaskTimeout    = 0    
        self.mainProgramFile    = ""
        self.mainSceneFile      = ""
        self.outputFormat       = ""
        self.resources          = []

class TaskState( QtCore.QObject ):
    #########################
    def __init__( self ):
        QtCore.QObject.__init__( self )
        self.definition     = TaskDefinition()

        self.status         = TaskStatus.notStarted
        self.progress       = 0.0
        self.computers      = {}
        self.remainingTime  = 0
        self.elapsedTime    = 0
        self.timeStarted    = 0
        self.resultPreview  = None

class ComputerState:
    #########################
    def __init__( self ):
        self.nodeId             = ""
        self.performance        = 0
        self.ipAddress          = ""
        self.subtaskState       = SubtaskState()

class SubtaskState:
    #########################
    def __init__( self ):
        self.subtaskDefinition  = ""
        self.subtaskId          = ""
        self.subtaskProgress    = 0.0
        self.subtaskRemTime     = 0
        self.subtaskStatus      = ""


class TaskStatus:
    notStarted  = "Not started"
    waiting     = "Waiting"
    starting    = "Starting"
    computing   = "Computing"
    finished    = "Finished"
    aborted     = "Aborted"
    failure     = "Failure"
    paused      = "Paused"

