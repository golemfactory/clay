import os

from apps.core.task.verificator import CoreFilesVerificator
from apps.dummy.resources.code_dir import computing


class DummyTaskVerificator(CoreFilesVerificator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.verification_options = {}

    # subtask_info is what sits in the task.subtasks_given[subtask_id"]
    # it is set in the query_extra_data
    def _verify_result(self, _subtask_id, subtask_info, file, _task):

        root, ext = os.path.splitext(file)
        ext = ext.lower()
        if ext != self.verification_options["result_extension"]:
            return False

        with open(file, "r") as f:
            result_data = f.read()

        if len(result_data) != self.verification_options["result_size"]:
            return False

        if self.verification_options["difficulty"] == 0:
            return True

        with open(self.verification_options["shared_data_files"][0], 'rU') as f:
            shared_data = f.read()

        input_data = shared_data + subtask_info["subtask_data"]

        return computing.check_pow(int(result_data, 16),
                                   input_data,
                                   self.verification_options["difficulty"])
