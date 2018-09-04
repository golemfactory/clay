from typing import Optional
from twisted.internet.defer import Deferred, inlineCallbacks
from golem.core.common import deadline_to_timeout


class VerificationTask:

    def __init__(self, subtask_id, deadline, kwargs) -> None:
        self.deadline = deadline
        self.kwargs = kwargs
        self.subtask_id = subtask_id

    def start(self, callback, verifier_class) -> Optional[Deferred]:
        verifier = verifier_class(self.kwargs)
        if deadline_to_timeout(self.deadline) > 0:
            if verifier.simple_verification(self.kwargs):
                return verifier.start_verification(self.kwargs, callback)
            else:
                verifier.verification_completed(callback)
        else:
            verifier.task_timeout(self.subtask_id)
        return None

    # Currently golem protocol does not allow for partial verification,
    # therefore we have to wait for any ongoing verification.
    @inlineCallbacks
    @staticmethod
    def stop(finished):
        yield finished
