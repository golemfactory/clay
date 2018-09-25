from golem_verificator.core_verifier import CoreVerifier
from typing import Callable, Dict, Optional, Any

import logging

logger = logging.getLogger(__name__)


class HoudiniTaskVerifier(CoreVerifier):
    # subtask_info is what sits in the task.subtasks_given["subtask_id"]
    # it is set in the query_extra_data
    def __init__(self, verification_data: Optional[Dict[str, Any]] = None) ->\
            None:
        super().__init__()

        self.results = verification_data

    def _verify_result(self, results: Dict[str, Any]):

        subtask_info = results["subtask_info"]
        results_files = results["results"]

        logger.info( "Houdini verifier, results: %s", str( results_files ) )

        return True