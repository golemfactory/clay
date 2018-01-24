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
        self._check_files(subtask_info, results, reference_data, resources,
                          self.verification_completed)

    def _check_files(self, subtask_info, results, reference_data, resources,
                     callback):
        for result in results:
            if os.path.isfile(result):
                if self._verify_result(subtask_info, result, reference_data,
                                       resources):
                    self.state = SubtaskVerificationState.VERIFIED
                    callback()
                    return
        self.state = SubtaskVerificationState.WRONG_ANSWER
        self.message = "No proper task result found"
        callback()

    def verification_completed(self):
        self.time_ended = datetime.utcnow()
        self.extra_data['results'] = self.results
        self.callback(subtask_id=self.subtask_info['subtask_id'],
                      verdict=self.state,
                      result=self._get_answer())

    # pylint: disable=unused-argument
    def _verify_result(self, subtask_info: dict, result: str,
                       reference_data: list, resources: list):
        """ Override this to change verification method
        """
        return True
