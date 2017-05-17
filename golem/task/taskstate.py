
class TaskState(object):
    def __init__(self):
        self.status = TaskStatus.notStarted
        self.progress = 0.0
        self.remaining_time = 0
        self.elapsed_time = 0
        self.time_started = 0
        self.payment_booked = False
        self.payment_settled = False
        self.outputs = []
        self.total_subtasks = 0
        self.subtask_states = {}

        self.extra_data = {}

    def __repr__(self):
        return '<TaskStatus: %r %.2f>' % (self.status, self.progress)


class ComputerState(object):
    def __init__(self):
        self.node_id = ""
        self.eth_account = ""
        self.performance = 0
        self.ip_address = ""
        self.port = 0
        self.node_name = ""
        self.price = 0


class SubtaskState(object):
    def __init__(self):
        self.subtask_definition = ""
        self.subtask_id = ""
        self.subtask_progress = 0.0
        self.time_started = 0
        self.deadline = 0
        self.extra_data = {}
        self.subtask_rem_time = 0
        self.subtask_status = ""
        self.value = 0
        self.stdout = ""
        self.stderr = ""
        self.results = []
        self.computation_time = 0

        self.computer = ComputerState()


class TaskStatus(object):
    notStarted = u"Not started"
    sending = u"Sending"
    waiting = u"Waiting"
    starting = u"Starting"
    computing = u"Computing"
    finished = u"Finished"
    aborted = u"Aborted"
    timeout = u"Timeout"
    paused = u"Paused"


class SubtaskStatus(object):
    waiting = u"Waiting"
    starting = u"Starting"
    resent = u"Failed - Resent"
    finished = u"Finished"
    failure = u"Failure"
    restarted = u"Restart"


class TaskTestStatus(object):
    started = u'Started'
    success = u'Success'
    error = u'Error'
