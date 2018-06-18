import os

from golem_verificator.core_verifier import CoreVerifier
from apps.dummy.resources.code_dir import computing


class DummyTaskVerifier(CoreVerifier):
    # subtask_info is what sits in the task.subtasks_given["subtask_id"]
    # it is set in the query_extra_data
    def __init__(self, callback, verification_data=None):
        super().__init__(callback)
        self.subtask_info = verification_data["subtask_info"]

    def _verify_result(self, verification_data):

        results = verification_data["results"]
        subtask_info = verification_data["subtask_info"]

        for result in results:
            _, ext = os.path.splitext(result)
            ext = ext.lower()
            if ext != subtask_info["result_extension"]:
                return False

            with open(result, "r") as f:
                result_data = f.read()

            if len(result_data) != subtask_info["result_size"]:
                return False

        if subtask_info["difficulty"] == 0:
            return True

        with open(subtask_info["shared_data_files"][0], 'rU') as f:
            shared_data = f.read()

        input_data = shared_data + subtask_info["subtask_data"]

        return computing.check_pow(int(result_data, 16),
                                   input_data,
                                   subtask_info["difficulty"])
