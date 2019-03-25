from enum import Enum, auto
import time
from typing import Dict

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
        self.subtask_states: Dict[str, SubtaskState] = {}
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


class SubtaskState(object):
    def __init__(self):
        self.subtask_id = ""
        self.subtask_progress = 0.0
        self.time_started = 0
        self.node_id = ""
        self.node_name = ""
        self.deadline = 0
        self.price = 0
        self.extra_data = {}
        # FIXME: subtask_rem_time is always equal 0 (#2562)
        self.subtask_rem_time = 0
        self.subtask_status: SubtaskStatus = SubtaskStatus.starting
        self.stdout = ""
        self.stderr = ""
        self.results = []

    def to_dictionary(self):
        return {
            'subtask_id': to_unicode(self.subtask_id),
            'node_id': to_unicode(self.node_id),
            'node_name': to_unicode(self.node_name),
            'status': self.subtask_status.value,
            'progress': self.subtask_progress,
            'time_started': self.time_started,
            'time_remaining': self.subtask_rem_time,
            'results': [to_unicode(r) for r in self.results],
            'stderr': to_unicode(self.stderr),
            'stdout': to_unicode(self.stdout),
        }

    def __repr__(self):
        return '<%s: %r>' % (
            type(self).__name__, self.to_dictionary()
        )


class TaskStatus(Enum):
    notStarted = "Not started"
    creatingDeposit = "Creating the deposit"
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

    def is_preparing(self) -> bool:
        return self in (
            self.notStarted,
            self.creatingDeposit,
        )

    def is_active(self) -> bool:
        return self in [self.sending, self.waiting,
                        self.starting, self.computing]


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

    def is_finishing(self) -> bool:
        return self in {self.downloading, self.verifying}


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
    VERIFYING = auto()

    def is_completed(self) -> bool:
        return self not in (
            SubtaskOp.ASSIGNED,
            SubtaskOp.RESULT_DOWNLOADING,
            SubtaskOp.RESTARTED,
            SubtaskOp.VERIFYING
        )


class OtherOp(Operation):
    """Ops that are not really interesting; for statistics anyway"""

    @staticmethod
    def unnoteworthy() -> bool:
        return True

    UNEXPECTED = auto()
    FRAME_RESTARTED = auto()
