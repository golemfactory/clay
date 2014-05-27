
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

class RendereInfo:
    #########################
    def __init__( self, name, defaults ):
        self.name           = name
        self.filters        = []
        self.pathTracers    = []
        self.outputFormats  = []
        self.defaults       = defaults

class RendererDefaults:
    #########################
    def __init__( self ):
        self.samplesPerPixel = 0
        self.outputFormat    = ""
        self.mainProgramFile = ""
        self.fullTaskTimeout = 0
        self.minSubtaskTime  = 0
        self.subtaskTimeout  = 0

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
        self.outputFormat       = ""
        self.resources          = []

class TaskState:
    #########################
    def __init__( self ):
        self.definition     = TaskDefinition()

        self.status         = ""
        self.progress       = 0.0
        self.computers      = {}
        self.remainingTime  = 0
        self.elapsedTime    = 0
        self.timeStarted    = 0
