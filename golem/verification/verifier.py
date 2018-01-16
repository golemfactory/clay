from collections import Callable
from datetime import datetime
from enum import Enum


class SubtaskVerificationState(Enum):
    UNKNOWN_SUBTASK = 0
    WAITING = 1
    IN_PROGRESS = 2
    VERIFIED = 3
    WRONG_ANSWER = 4
    NOT_SURE = 5


class Verifier:

    def __init__(self, callback: Callable):
        self.callback = callback

    def start_verification(self, subtask_info: dict, reference_data: list,
                           resources: list, results: list) -> None:
        raise NotImplementedError

    def stop_verification(self):
        raise NotImplementedError


class StateVerifier(Verifier):

    active_status = [SubtaskVerificationState.WAITING,
                     SubtaskVerificationState.IN_PROGRESS]

    def __init__(self, callback: Callable):
        super(StateVerifier, self).__init__(callback)
        self.subtask_info = {}
        self.reference_data = []
        self.resources = []
        self.results = []
        self.state = SubtaskVerificationState.UNKNOWN_SUBTASK
        self.time_started = None
        self.time_ended = None
        self.extra_data = {}
        self.message = ""
        self.computer = None

    def start_verification(self, subtask_info: dict, reference_data: list,
                           resources: list, results: list):
        self.subtask_info = subtask_info
        self.reference_data = reference_data
        self.resources = resources
        self.results = results
        self.state = SubtaskVerificationState.WAITING
        self.time_started = datetime.utcnow()
        self.time_ended = None

    def stop_verification(self):
        self.time_ended = datetime.utcnow()

        if self.state in self.active_status:
            self.state = SubtaskVerificationState.NOT_SURE
        self.message = "Verification was stopped"
        answer = self._get_answer()
        self.callback(subtask_id=self.subtask_info['subtask_id'],
                      verdict=self.state,
                      results=answer)
        self._clear_state()

    def _clear_state(self):
        self.subtask_info = {}
        self.reference_data = []
        self.resources = []
        self.results = []
        self.state = SubtaskVerificationState.UNKNOWN_SUBTASK
        self.time_started = None
        self.time_ended = None
        self.extra_data = {}

    def _get_answer(self):
        return {'reference_data': self.reference_data,
                'message': self.message,
                'time_started': self.time_started,
                'time_ended': self.time_ended,
                'extra_data': self.extra_data}
