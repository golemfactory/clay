from enum import Enum, auto
import functools
import time
from typing import Dict, Optional

from golem_messages import datastructures
from golem_messages import validators


class TaskState:
    # pylint: disable=too-many-instance-attributes

    def __init__(self, task=None) -> None:
        self.status = TaskStatus.creating
        self.status_message: Optional[str] = None
        self.progress = 0.0
        self.remaining_time = 0
        self.elapsed_time = 0
        self.time_started = 0.0
        self.payment_booked = False
        self.payment_settled = False
        self.subtask_states: Dict[str, SubtaskState] = {}
        self.resource_hash = None
        self.package_hash = None
        self.package_path = None
        self.package_size = None
        self.extra_data: Dict = {}
        self.last_update_time = time.time()
        self.estimated_fee = 0

        if task:
            self.outputs = task.get_output_names()
            self.subtasks_count = task.get_total_tasks()
            self.estimated_cost = task.price
        else:
            self.outputs = []
            self.subtasks_count = 0
            self.estimated_cost = 0

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
            'status_message': getattr(self, 'status_message', None),
            'estimated_cost': getattr(self, 'estimated_cost', None),
            'estimated_fee': getattr(self, 'estimated_fee', None)
        }


class SubtaskStatus(Enum):
    starting = "Starting"
    downloading = "Downloading"
    verifying = "Verifying"
    resent = "Failed - Resent"
    finished = "Finished"
    failure = "Failure"
    restarted = "Restart"
    cancelled = "Cancelled"

    def is_computed(self) -> bool:
        return self in [self.starting, self.downloading]

    def is_active(self) -> bool:
        return self in [self.starting, self.downloading, self.verifying]

    def is_finished(self) -> bool:
        return self == self.finished

    def is_finishing(self) -> bool:
        return self in {self.downloading, self.verifying}


validate_varchar_inf = functools.partial(
    validators.validate_varchar,
    max_length=float('infinity'),
)


class SubtaskState(datastructures.Container):
    __slots__ = {
        'subtask_id': (validators.validate_varchar128, ),
        'progress': (
            functools.partial(
                validators.fail_unless,
                check=lambda x: isinstance(x, float),
                fail_msg="Should be a float",
            ),
        ),
        'time_started': (validators.validate_integer, ),
        'node_id': (validators.validate_varchar128, ),
        'node_name': (validate_varchar_inf, ),
        'deadline': (validators.validate_integer, ),
        'price': (validators.validate_integer, ),
        'extra_data': (),
        'status': (
            functools.partial(
                validators.fail_unless,
                check=lambda x: isinstance(x, (str, SubtaskStatus)),
                fail_msg="Should be str or SubtaskStatus",
            ),
        ),
        'stdout': (validate_varchar_inf, ),
        'stderr': (validate_varchar_inf, ),
        'results': (
            functools.partial(
                validators.fail_unless,
                check=lambda x: isinstance(x, list),
                fail_msg="Should be a list",
            ),
        ),
    }

    DEFAULTS = {
        'progress': lambda: 0.0,
        'time_started': lambda: int(time.time()),
        'node_name': lambda: "",
        'extra_data': lambda: {},
        'status': lambda: SubtaskStatus.starting,
        'stdout': lambda: "",
        'stderr': lambda: "",
        'results': lambda: [],
    }

    REQUIRED = frozenset((
        'subtask_id',
        'node_id',
        'deadline',
        'price',
    ))

    @classmethod
    def deserialize_status(cls, value):
        if isinstance(value, SubtaskStatus):
            return value
        return SubtaskStatus(value)

    @classmethod
    def serialize_status(cls, value: SubtaskStatus):
        return value.value


class TaskStatus(Enum):
    creating = "Creating"
    errorCreating = "Error creating"
    testing = "Testing"
    errorTesting = "Error testing"
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

    def is_creating(self) -> bool:
        return self in [self.creating, self.errorCreating]

    def is_completed(self) -> bool:
        return self in [self.finished, self.aborted,
                        self.timeout, self.restarted]

    def is_preparing(self) -> bool:
        return self in (
            self.creating,
            self.notStarted,
            self.creatingDeposit,
        )

    def is_active(self) -> bool:
        return self in [self.sending, self.waiting,
                        self.starting, self.computing]


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
