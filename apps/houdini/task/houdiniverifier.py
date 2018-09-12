from golem_verificator.core_verifier import CoreVerifier
from typing import Callable, Dict, Optional, Any


class HoudiniTaskVerifier(CoreVerifier):
    # subtask_info is what sits in the task.subtasks_given["subtask_id"]
    # it is set in the query_extra_data
    def __init__(self, verification_data: Optional[Dict[str, Any]] = None) ->\
            None:
        super().__init__()

    def _verify_result(self, results: Dict[str, Any]):
        return [True]