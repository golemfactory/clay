import time

class TaskState:
    #########################
    def __init__(self):

        self.status         = TaskStatus.notStarted
        self.progress       = 0.0
        self.remainingTime  = 0
        self.elapsedTime    = 0
        self.timeStarted    = 0
        self.paymentBooked  = False
        self.paymentSettled = False

        self.subtaskStates  = {}

        self.extraData      = {}

    #########################
    def getSubtaskState(self, subtask_id):
        if subtask_id in self.subtaskStates:
            return self.subtaskStates[ subtask_id ]
        else:
            return None

    #########################
    def getSubtaskStateForComputer(self, node_id):

        subtasksStates = []

        for k in self.subtaskStates:
            ss = self.subtaskStates[ k ]
            if ss.computer.node_id == node_id:
                subtasksStates.append(ss)


class ComputerState:
    #########################
    def __init__(self):
        self.node_id             = ""
        self.eth_account         = ""
        self.performance        = 0
        self.ipAddress          = ""
        self.port               = 0
        self.key_id              = 0

class SubtaskState:
    #########################
    def __init__(self):
        self.subtaskDefinition  = ""
        self.subtask_id          = ""
        self.subtaskProgress    = 0.0
        self.timeStarted        = 0
        self.ttl                = 0
        self.last_checking       = time.time()
        self.extraData          = {}
        self.subtaskRemTime     = 0
        self.subtaskStatus      = ""
        self.value              = 0


        self.computer           = ComputerState()


class TaskStatus:
    notStarted  = "Not started"
    sending     = "Sending"
    waiting     = "Waiting"
    starting    = "Starting"
    computing   = "Computing"
    finished    = "Finished"
    aborted     = "Aborted"
    failure     = "Failure"
    paused      = "Paused"

class SubtaskStatus:
    waiting     = "Waiting"
    starting    = "Starting"
    resent      = "Failed - Resent"
    finished    = "Finished"
    failure     = "Failure"
