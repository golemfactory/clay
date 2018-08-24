from twisted.internet.defer import Deferred
from golem.core.common import deadline_to_timeout

class VerificationTask:

    def __init__(self, verifier_class, subtask_id, deadline, kwargs):
        self.verifier = verifier_class(kwargs)
        self.deadline = deadline
        self.kwargs = kwargs
        self.subtask_id = subtask_id

    def start(self, callback):
        if deadline_to_timeout(self.deadline) > 0:
            if self.verifier.simple_verification(self.kwargs):
                self.verifier.start_verification(self.kwargs, callback)
            else:
                callback(self.verifier.verification_completed())
        else:
            self.verifier.task_timeout(self.subtask_id)
            raise Exception("Task deadline passed")

    def stop(self):
        pass

    def cancel(self):
        pass