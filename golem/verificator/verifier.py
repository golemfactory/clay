import logging
from datetime import datetime
from enum import IntEnum

logger = logging.getLogger("verifier")


class SubtaskVerificationState(IntEnum):
    UNKNOWN_SUBTASK = 0
    WAITING = 1
    IN_PROGRESS = 2
    VERIFIED = 3
    WRONG_ANSWER = 4
    NOT_SURE = 5
    TIMEOUT = 6


class Verifier:

    def start_verification(self, subtask_info: dict,
                           resources: list, results: list) -> None:
        raise NotImplementedError


class StateVerifier(Verifier):

    active_status = [SubtaskVerificationState.WAITING,
                     SubtaskVerificationState.IN_PROGRESS]

    def __init__(self):
        super(StateVerifier, self).__init__()
        self.subtask_info = {}
        self.resources = []
        self.results = []
        self.state = SubtaskVerificationState.UNKNOWN_SUBTASK
        self.time_started = None
        self.time_ended = None
        self.extra_data = {}
        self.message = ""
        self.computer = None

    def task_timeout(self, subtask_id):
        logger.warning("Task %r after deadline", subtask_id)
        if self.time_started is not None:
            self.time_ended = datetime.utcnow()
            if self.state in self.active_status:
                self.state = SubtaskVerificationState.NOT_SURE
            self.message = "Verification was stopped"
        else:
            self.time_started = self.time_ended = datetime.utcnow()
            self.state = SubtaskVerificationState.TIMEOUT
            self.message = "Verification never ran, task timed out"

        state = self.state
        answer = self._get_answer()
        self._clear_state()
        return subtask_id, state, answer

    def _clear_state(self):
        self.subtask_info = {}
        self.resources = []
        self.results = []
        self.state = SubtaskVerificationState.UNKNOWN_SUBTASK
        self.time_started = None
        self.time_ended = None
        self.extra_data = {}

    def _get_answer(self):
        return {'message': self.message,
                'time_started': self.time_started,
                'time_ended': self.time_ended,
                'extra_data': self.extra_data}

    def _check_computer(self):
        if not self.computer:
            self.state = SubtaskVerificationState.NOT_SURE
            self.message = "No computer available to verify data"
            return False
        return True

    def _wait_for_computer(self):
        if not self.computer.wait():
            self.state = SubtaskVerificationState.NOT_SURE
            self.message = "Computation was not run correctly"
            return False
        return True
