import os
from typing import Dict, Optional, Any

from golem.verifier.core_verifier import CoreVerifier
from apps.dummy.resources.code_dir import computing


class DummyTaskVerifier(CoreVerifier):
    # subtask_info is what sits in the task.subtasks_given["subtask_id"]
    # it is set in the query_extra_data
    def __init__(self, verification_data: Dict[str, Any]) -> None:
        super().__init__(verification_data)
        self.subtask_info = verification_data["subtask_info"]

    def _verify_result(self, results: Dict[str, Any]):

        subtask_info = results["subtask_info"]
        results = results["results"]

        ret_list = []

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

            ret_list.append(computing.check_pow(int(result_data, 16),
                                                input_data,
                                                subtask_info["difficulty"]))
            return ret_list
