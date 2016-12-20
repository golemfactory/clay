from golem.task.taskstate import TaskState


class GNRTaskDefinition(object):

    def __init__(self):
        self.task_id = ""
        self.full_task_timeout = 0
        self.subtask_timeout = 0

        self.resources = set()
        self.estimated_memory = 0

        self.total_subtasks = 0
        self.optimize_total = False
        self.main_program_file = ""
        self.task_type = None

        self.max_price = 0

        self.verification_options = None
        self.options = GNROptions
        self.docker_images = None


advanceVerificationTypes = ['forAll', 'forFirst', 'random']


class AdvanceVerificationOptions(object):
    def __init__(self):
        self.type = 'forFirst'


class GNRTaskState(object):
    def __init__(self):
        self.definition = GNRTaskDefinition()
        self.task_state = TaskState()


class GNROptions(object):
    def __init__(self):
        self.name = ''
