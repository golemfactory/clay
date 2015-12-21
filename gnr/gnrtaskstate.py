from golem.task.taskstate import TaskState


class GNRTaskDefinition:
    def __init__(self):
        self.task_id = ""
        self.full_task_timeout = 0
        self.subtask_timeout = 0
        self.min_subtask_time = 0

        self.resources = set()
        self.estimated_memory = 0

        self.total_subtasks = 0
        self.optimize_total = False
        self.main_program_file = ""
        self.task_type = None

        self.verification_options = None
        self.options = GNROptions


advanceVerificationTypes = ['forAll', 'forFirst', 'random']


class AdvanceVerificationOptions:
    def __init__(self):
        self.type = 'forFirst'


class GNRTaskState:
    def __init__(self):
        self.definition = GNRTaskDefinition()
        self.task_state = TaskState()


class GNROptions:
    def __init__(self):
        self.name = ''
