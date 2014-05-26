
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

class TaskStatus:
    #########################
    def __init__( self ):
        self.id             = ""
        self.status         = ""
        self.progress       = 0.0
        self.computers      = {}
        self.remainingTime  = 0
        self.elapsedTime    = 0
        self.minPower       = 0
        self.minSubtask     = 0
        self.maxSubtask     = 0
        self.subtaskTimeout = 0

        self.resolution         = [ 0, 0 ]
        self.renderer           = ""
        self.algorithmType      = ""
        self.pixelFilter        = ""
        self.samplesPerPixelCount = 0
        self.outputFile         = ""
        self.taskResources      = []
        self.fullTaskTimeout    = 0
        self.timeStarted        = 0
