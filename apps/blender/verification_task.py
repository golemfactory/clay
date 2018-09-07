from typing import Optional
from twisted.internet.defer import Deferred, inlineCallbacks
from golem.core.common import deadline_to_timeout


class VerificationTask:

    def __init__(self, subtask_id, deadline, kwargs) -> None:
        self.deadline = deadline
        self.kwargs = kwargs
        self.subtask_id = subtask_id
        self.verifier = None

    def start(self, verifier_class) -> Optional[Deferred]:
        self.verifier = verifier_class(self.kwargs)
        if deadline_to_timeout(self.deadline) > 0:
            if self.verifier.simple_verification(self.kwargs):
                return self.verifier.start_verification(self.kwargs)
            deferred = Deferred()
            deferred.callback(self.verifier.verification_completed())
            return deferred
        else:
            self.verifier.task_timeout(self.subtask_id)
        return None

    def get_results(self):
        return self.verifier.verification_completed()

    # Currently golem protocol does not allow for partial verification,
    # therefore we have to wait for any ongoing verification.
    def stop(self, finished):
        self.verifier.stop()
        finished.cancel()
