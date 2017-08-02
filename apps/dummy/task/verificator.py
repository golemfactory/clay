import os

from golem.core.common import HandleKeyError
from apps.dummy.computing import check_pow

from apps.core.task.verificator import CoreVerificator, SubtaskVerificationState


class DummyTaskVerificator(CoreVerificator):

    @CoreVerificator.handle_key_error_for_state
    def verify(self, subtask_id, subtask_info, tr_files, task):

        self._check_files(subtask_id, subtask_info, tr_files, task)
        return self.ver_states[subtask_id]

    def _check_files(self, subtask_id, subtask_info, tr_files, task):
        for tr_file in tr_files:
            if os.path.isfile(tr_file):
                with open(tr_file, "r") as f:
                    result = f.read()
                    if self.verify_result(subtask_info, result):
                        self.ver_states[subtask_id] = SubtaskVerificationState.VERIFIED
                return
        self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER

    def verify_result(self, subtask_info, result):
        '''
        Actual verification of result happens here
        :param result: Result of the computation
        :return: bool: True if the result was OK
        '''

        if len(result) != self.verification_options.result_size:
            return False

        if self.verification_options.difficulty == 0:
            return True


        with open(self.verification_options.shared_data_file, 'r') as f:
            input_data = f.read()

        input_data += subtask_info.extra_data.subtask_data

        return check_pow(long(result, 16),
                         input_data,
                         self.verification_options.difficulty)