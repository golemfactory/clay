import hashlib
from typing import Dict, Optional, Any

from golem_verificator.core_verifier import CoreVerifier


class Dummy2TaskVerifier(CoreVerifier):
    # subtask_info is what sits in the task.subtasks_given["subtask_id"]
    # it is set in the query_extra_data
    def __init__(self, verification_data: Optional[Dict[str, Any]] = None) ->\
            None:
        super().__init__()
        if verification_data:
            self.subtask_info = verification_data["subtask_info"]
        else:
            self.subtask_info = None

    def _verify_result(self, results: Dict[str, Any]):

        subtask_info = results["subtask_info"]
        result = results["results"][0]

        # Workaround for inability to provide parent_task reference for
        # Dummy2Task object
        if subtask_info['verification']:
            return True

        # Accessing owner task is required because it keeps randomly generated
        # artificial passwords for each subtask
        parent_task = subtask_info['parent_task']
        subtask_offset = subtask_info['start_task'] - 1

        original_passwds = set(
            parent_task.get_passwds_for_bucket(subtask_offset))

        with open(result, 'r') as f:
            result_passwds = set(f.read().split())

        # Check mismatch reason
        if not original_passwds == result_passwds:
            # Mismatch subset must be a single element set containing the
            # password of interest otherwise result is malicious
            mismatch_subset = result_passwds.difference(original_passwds)
            if len(mismatch_subset) != 1:
                return False
            realpasswd = mismatch_subset.pop()
            sha = hashlib.sha256()
            sha.update(realpasswd.encode())
            if sha.hexdigest() != parent_task.password_hash:
                return False
            parent_task.real_password = realpasswd

        return True
