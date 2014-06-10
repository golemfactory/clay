class TaskState:
    #########################
    def __init__( self ):

        self.status         = TaskStatus.notStarted
        self.progress       = 0.0
        self.computers      = []
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
