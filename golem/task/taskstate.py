from enum import Enum, auto
import time
from typing import Optional

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
        self.subtasks_count = 0
        self.subtask_states = {}
        self.resource_hash = None
        self.package_hash = None
        self.package_path = None
        self.package_size = None
        self.extra_data = {}
        self.last_update_time = time.time()
        self.estimated_cost = 0
        self.estimated_fee = 0

    def __setattr__(self, key, value):
        super().__setattr__(key, value)
        # Set last update time when changing status to other than 'restarted'
        # (user interaction)
        if key == 'status' and value != TaskStatus.restarted:
            self.last_update_time = time.time()

    def __repr__(self):
        return '<TaskStatus: %r %.2f>' % (self.status, self.progress)

    def to_dictionary(self):
        return {
            'time_started': self.time_started,
            'time_remaining': self.remaining_time,
            'last_updated': getattr(self, 'last_update_time', None),
            'status': self.status.value,
            'estimated_cost': getattr(self, 'estimated_cost', None),
            'estimated_fee': getattr(self, 'estimated_fee', None)
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
        # FIXME: subtask_rem_time is always equal 0 (#2562)
        self.subtask_rem_time = 0
        self.subtask_status: Optional[SubtaskStatus] = None
        self.value = 0
        self.stdout = ""
        self.stderr = ""
        self.results = []

        self.computer = ComputerState()

    def to_dictionary(self):
        return {
            'subtask_id': to_unicode(self.subtask_id),
            'node_name': to_unicode(self.computer.node_name),
            'node_id': to_unicode(self.computer.node_id),
            'node_performance': to_unicode(self.computer.performance),
            'node_ip_address': to_unicode(self.computer.ip_address),
            'node_port': self.computer.port,
            'status': self.subtask_status.value,
            'progress': self.subtask_progress,
            'time_started': self.time_started,
            'time_remaining': self.subtask_rem_time,
            'results': [to_unicode(r) for r in self.results],
            'stderr': to_unicode(self.stderr),
            'stdout': to_unicode(self.stdout),
            'description': self.subtask_definition,
        }


class TaskStatus(Enum):
    notStarted = "Not started"
    sending = "Sending"
    waiting = "Waiting"
    starting = "Starting"
    computing = "Computing"
    finished = "Finished"
    aborted = "Aborted"
    timeout = "Timeout"
    restarted = "Restart"

    def is_completed(self) -> bool:
        return self in [self.finished, self.aborted,
                        self.timeout, self.restarted]


class SubtaskStatus(Enum):
    starting = "Starting"
    downloading = "Downloading"
    verifying = "Verifying"
    resent = "Failed - Resent"
    finished = "Finished"
    failure = "Failure"
    restarted = "Restart"

    def is_computed(self) -> bool:
        return self in [self.starting, self.downloading]

    def is_active(self) -> bool:
        return self in [self.starting, self.downloading, self.verifying]

    def is_finished(self) -> bool:
        return self == self.finished


class TaskTestStatus(Enum):
    started = 'Started'
    success = 'Success'
    error = 'Error'


class Operation(Enum):
    @staticmethod
    def task_related() -> bool:
        return False

    @staticmethod
    def subtask_related() -> bool:
        return False

    @staticmethod
    def unnoteworthy() -> bool:
        return False

    def is_completed(self) -> bool:
        pass


class TaskOp(Operation):
    """Ops that result in storing of task level information"""

    @staticmethod
    def task_related() -> bool:
        return True

    def is_completed(self) -> bool:
        return self in [
            TaskOp.FINISHED,
            TaskOp.NOT_ACCEPTED,
            TaskOp.TIMEOUT,
            TaskOp.RESTARTED,
            TaskOp.ABORTED]

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

    @staticmethod
    def subtask_related() -> bool:
        return True

    ASSIGNED = auto()
    RESULT_DOWNLOADING = auto()
    NOT_ACCEPTED = auto()
    FINISHED = auto()
    FAILED = auto()
    TIMEOUT = auto()
    RESTARTED = auto()

    def is_completed(self) -> bool:
        return self not in (
            SubtaskOp.ASSIGNED,
            SubtaskOp.RESULT_DOWNLOADING,
            SubtaskOp.RESTARTED
        )


class OtherOp(Operation):
    """Ops that are not really interesting; for statistics anyway"""

    @staticmethod
    def unnoteworthy() -> bool:
        return True

    UNEXPECTED = auto()
    FRAME_RESTARTED = auto()
