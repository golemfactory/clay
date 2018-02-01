from enum import Enum, auto

from golem.core.common import to_unicode


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
        self.resource_hash = None

        self.extra_data = {}

    def __repr__(self):
        return '<TaskStatus: %r %.2f>' % (self.status, self.progress)

    def to_dictionary(self):
        return {
            'time_started': self.time_started,
            'time_remaining': self.remaining_time,
            'status': to_unicode(self.status)
        }


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

    def to_dictionary(self):
        return {
            'subtask_id': to_unicode(self.subtask_id),
            'node_name': to_unicode(self.computer.node_name),
            'node_id': to_unicode(self.computer.node_id),
            'node_performance': to_unicode(self.computer.performance),
            'node_ip_address': to_unicode(self.computer.ip_address),
            'node_port': self.computer.port,
            'status': to_unicode(self.subtask_status),
            'progress': self.subtask_progress,
            'time_started': self.time_started,
            'time_remaining': self.subtask_rem_time,
            'results': [to_unicode(r) for r in self.results],
            'stderr': to_unicode(self.stderr),
            'stdout': to_unicode(self.stdout),
            'description': self.subtask_definition,
        }


class TaskStatus(object):
    notStarted = "Not started"
    sending = "Sending"
    waiting = "Waiting"
    starting = "Starting"
    computing = "Computing"
    finished = "Finished"
    aborted = "Aborted"
    timeout = "Timeout"
    restarted = "Restart"


class SubtaskStatus(object):
    starting = "Starting"
    downloading = "Downloading"
    resent = "Failed - Resent"
    finished = "Finished"
    failure = "Failure"
    restarted = "Restart"

    @classmethod
    def is_computed(cls, status):
        return status in [cls.starting, cls.downloading]


class TaskTestStatus(object):
    started = 'Started'
    success = 'Success'
    error = 'Error'


class Operation(Enum):
    pass


class TaskOp(Operation):
    """Ops that result in storing of task level information"""
    WORK_OFFER_RECEIVED = auto()
    CREATED = auto()
    STARTED = auto()
    FINISHED = auto()
    NOT_ACCEPTED = auto()
    TIMEOUT = auto()
    RESTARTED = auto()
    ABORTED = auto()
    RESTORED = auto()


class SubtaskOp(Operation):
    """Ops that result in storing of subtask level information;
    subtask_id needs to be set for them"""
    ASSIGNED = auto()
    RESULT_DOWNLOADING = auto()
    NOT_ACCEPTED = auto()
    FINISHED = auto()
    FAILED = auto()
    TIMEOUT = auto()
    RESTARTED = auto()


class OtherOp(Operation):
    """Ops that are not really interesting; for statistics anyway"""
    UNEXPECTED = auto()
    FRAME_RESTARTED = auto()
