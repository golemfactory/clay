class TaskState:
    #########################
    def __init__( self ):

        self.status         = TaskStatus.notStarted
        self.progress       = 0.0
        self.remainingTime  = 0
        self.elapsedTime    = 0
        self.timeStarted    = 0
        self.resultPreview  = None

        self.subtaskStates  = {}

    #########################
    def getSubtaskState( self, subtaskId ):
        if subtaskId in self.subtaskStates:
            return self.subtaskStates[ subtaskId ]
        else:
            return None

    #########################
    def getSubtaskStateForComputer( self, nodeId ):

        subtasksStates = []

        for k in self.subtaskStates:
            ss = self.subtaskStates[ k ]
            if ss.computer.nodeId == nodeId:
                subtasksStates.append( ss )


class ComputerState:
    #########################
    def __init__( self ):
        self.nodeId             = ""
        self.performance        = 0
        self.ipAddress          = ""

class SubtaskState:
    #########################
    def __init__( self ):
        self.subtaskDefinition  = ""
        self.subtaskId          = ""
        self.subtaskProgress    = 0.0
        self.subtaskRemTime     = 0
        self.subtaskStatus      = ""

        self.computer           = ComputerState()


class TaskStatus:
    notStarted  = "Not started"
    waiting     = "Waiting"
    starting    = "Starting"
    computing   = "Computing"
    finished    = "Finished"
    aborted     = "Aborted"
    failure     = "Failure"
    paused      = "Paused"
