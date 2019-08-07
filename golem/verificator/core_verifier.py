import logging
import os
from datetime import datetime
from .verifier import (StateVerifier, SubtaskVerificationState)

from twisted.internet.defer import Deferred

logger = logging.getLogger("golem.verificator.core_verifier")


class CoreVerifier(StateVerifier):

    def __init__(self):
        super().__init__()

    def start_verification(self, verification_data):
        self.time_started = datetime.utcnow()
        self.subtask_info = verification_data["subtask_info"]
        if self._verify_result(verification_data):
            self.state = SubtaskVerificationState.VERIFIED
            finished = Deferred()
            finished.callback(self.verification_completed())
            return finished

    def simple_verification(self, verification_data):
        results = verification_data["results"]
        if not results:
            self.state = SubtaskVerificationState.WRONG_ANSWER
            return False

        for result in results:
            if not os.path.isfile(result) or not\
                    self._verify_result(verification_data):
                self.message = "No proper task result found"
                self.state = SubtaskVerificationState.WRONG_ANSWER
                return False

        self.state = SubtaskVerificationState.VERIFIED
        return True

    def verification_completed(self):
        self.time_ended = datetime.utcnow()
        self.extra_data['results'] = self.results
        return self.subtask_info['subtask_id'], self.state, self._get_answer()

    # pylint: disable=unused-argument
    def _verify_result(self, results):
        """ Override this to change verification method
        """
        return True
