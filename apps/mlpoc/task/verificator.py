import os

from apps.core.task.verificator import CoreVerificator
from apps.dummy.resources.code_dir import computing

# TODO Verificator should be run inside docker
class MLPOCTaskVerificator(CoreVerificator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.verification_options = {}

    # subtask_info is what sits in the task.subtasks_given[subtask_id"]
    # it is set in the query_extra_data
    def _verify_result(self, _subtask_id, subtask_info, file, _task):

        if self.verification_options["no_verification"]:
            return True

        root, ext = os.path.splitext(file)
        ext = ext.lower()
        if ext != self.verification_options["result_extension"]:
            return False

        with open(file, "r") as f:
            result_data = f.read()

        # TODO