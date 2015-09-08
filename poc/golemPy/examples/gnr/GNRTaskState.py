from golem.task.TaskState import TaskState

###########################################################################
class GNRTaskDefinition:
    def __init__(self):
        self.task_id = ""
        self.fullTaskTimeout = 0
        self.subtask_timeout     = 0
        self.minSubtaskTime     = 0

        self.resources = set()
        self.estimated_memory    = 0

        self.totalSubtasks      = 0
        self.optimizeTotal      = False
        self.mainProgramFile    = ""
        self.taskType           = None

        self.verificationOptions = None
        self.options = GNROptions

###########################################################################

advanceVerificationTypes = [ 'forAll', 'forFirst', 'random' ]

class AdvanceVerificationOptions:
    #########################
    def __init__(self):
        self.type = 'forFirst'

###########################################################################
class GNRTaskState:
    #########################
    def __init__(self):
        self.definition     = GNRTaskDefinition()
        self.taskState      = TaskState()

class GNROptions:
    #########################
    def __init__(self):
        self.name = ''