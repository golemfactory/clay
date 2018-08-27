from typing import Optional
from twisted.internet.defer import Deferred, inlineCallbacks
from golem.core.common import deadline_to_timeout

class VerificationTask:

    def __init__(self, verifier_class, subtask_id, deadline, kwargs):
        self.verifier = verifier_class(kwargs)
        self.deadline = deadline
        self.kwargs = kwargs
        self.subtask_id = subtask_id

    def start(self, callback) -> Optional[Deferred]:
        if deadline_to_timeout(self.deadline) > 0:
            if self.verifier.simple_verification(self.kwargs):
                return self.verifier.start_verification(self.kwargs, callback)
            else:
                self.verifier.verification_completed(callback)
        else:
            self.verifier.task_timeout(self.subtask_id)

    # Currently golem protocol does not allow for partial verification,
    # therefore we have to wait for any ongoing verification.
    @inlineCallbacks
    def stop(self):
        yield self.verifier.finished
