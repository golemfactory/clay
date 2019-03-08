import logging
import os
from datetime import datetime

from twisted.internet.defer import Deferred

from golem.verificator.constants import SubtaskVerificationState

logger = logging.getLogger('golem.verificator.core_verifier')


class CoreVerifier:  # pylint: disable=too-many-instance-attributes

    active_status = [SubtaskVerificationState.WAITING,
                     SubtaskVerificationState.IN_PROGRESS]

    def __init__(self):
        self.subtask_info = {}
        self.resources = []
        self.results = []
        self.state = SubtaskVerificationState.UNKNOWN_SUBTASK
        self.time_started = None
        self.time_ended = None
        self.extra_data = {}
        self.message = ""
        self.computer = None

    def start_verification(self, verification_data):
        self.time_started = datetime.utcnow()
        self.subtask_info = verification_data['subtask_info']
        if self._verify_result(verification_data):
            self.state = SubtaskVerificationState.VERIFIED
            finished = Deferred()
            finished.callback(self.verification_completed())
            return finished

    def simple_verification(self, verification_data):
        results = verification_data['results']
        if not results:
            self.state = SubtaskVerificationState.WRONG_ANSWER
            return False

        for result in results:
            if not os.path.isfile(result) or not\
                    self._verify_result(verification_data):
                self.message = 'No proper task result found'
                self.state = SubtaskVerificationState.WRONG_ANSWER
                return False

        self.state = SubtaskVerificationState.VERIFIED
        return True

    def verification_completed(self):
        self.time_ended = datetime.utcnow()
        self.extra_data['results'] = self.results
        return self.subtask_info['subtask_id'], self.state, self._get_answer()

    def task_timeout(self, subtask_id):
        logger.warning('Task %r after deadline', subtask_id)
        if self.time_started is not None:
            self.time_ended = datetime.utcnow()
            if self.state in self.active_status:
                self.state = SubtaskVerificationState.NOT_SURE
            self.message = 'Verification was stopped'
        else:
            self.time_started = self.time_ended = datetime.utcnow()
            self.state = SubtaskVerificationState.TIMEOUT
            self.message = 'Verification never ran, task timed out'

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

    # pylint: disable=unused-argument
    def _verify_result(self, results):
        """ Override this to change verification method. """
        return True
