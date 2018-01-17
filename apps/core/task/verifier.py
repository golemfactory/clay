from datetime import datetime
import os

from golem.verification.verifier import (StateVerifier,
                                         SubtaskVerificationState)


class CoreVerifier(StateVerifier):

    def start_verification(self, subtask_info: dict, reference_data: list,
                           resources: list, results: list):
        super(CoreVerifier, self).start_verification(subtask_info,
                                                     reference_data,
                                                     resources,
                                                     results)
        self._check_files(subtask_info, results, reference_data, resources)
        self.time_ended = datetime.utcnow()
        self.extra_data['results'] = self.results
        self.callback(subtask_id=self.subtask_info['subtask_id'],
                      verdict=self.state,
                      result=self._get_answer())
        self._clear_state()

    def _check_files(self, subtask_info, results, reference_data, resources):
        for result in results:
            if os.path.isfile(result):
                if self._verify_result(subtask_info, result, reference_data,
                                       resources):
                    self.state = SubtaskVerificationState.VERIFIED
                    return
        self.state = SubtaskVerificationState.WRONG_ANSWER
        self.message = "No proper task result found"

    # pylint: disable=unused-argument
    def _verify_result(self, subtask_info, result, reference_data, resources):
        """ Override this to change verification method
        """
        return True
