import os

from apps.core.task.verificator import CoreVerificator, SubtaskVerificationState
from apps.dummy.resources.code_dir import computing


class DummyTaskVerificator(CoreVerificator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.verification_options = {}

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

    # subtask_info is what sits in the task.subtasks_given[subtask_id"]
    # it is set in the query_extra_data
    def verify_result(self, subtask_info, result_data):
        '''
        Actual verification of result happens here
        :param result: Result of the computation
        :return: bool: True if the result was OK
        '''

        if len(result_data) != self.verification_options["result_size"]:
            return False

        if self.verification_options["difficulty"] == 0:
            return True

        with open(self.verification_options["shared_data_files"][0], 'r') as f:
            input_data = f.read()

        input_data += subtask_info["subtask_data"]

        return computing.check_pow(int(result_data, 16),
                                   input_data,
                                   self.verification_options["difficulty"])
