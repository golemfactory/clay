import logging
from typing import Optional, Any
from twisted.internet.defer import Deferred, gatherResults
from golem.core.common import deadline_to_timeout
from apps.blender.blender_reference_generator import BlenderReferenceGenerator

logger = logging.getLogger("apps.blender.verification.task")


class VerificationTask:

    def __init__(self, subtask_id, deadline, kwargs) -> None:
        self.deadline = deadline
        self.kwargs = kwargs
        self.subtask_id = subtask_id
        self.verifier: Any = None
        self.reference_generator = BlenderReferenceGenerator()
        self.finished = Deferred()
        self.all_crop_finished = Deferred()

    def start(self, verifier_class) -> Optional[Deferred]:
        self.verifier = verifier_class(self.kwargs)
        self.verifier.initialize(self.kwargs)
        if deadline_to_timeout(self.deadline) > 0:
            if self.verifier.simple_verification(self.kwargs):
                finished_crops = self.reference_generator.render_crops(
                    self.kwargs['resources'],
                    self.kwargs["subtask_info"],
                    3)
                for d in finished_crops:
                    d.addCallback(self.__crop_rendered)
                    d.addErrback(self.__crop_render_failure)
                self.all_crop_finished = gatherResults(finished_crops)
                self.all_crop_finished.addCallback(self.start_verification)
                self.all_crop_finished.addErrback(self.failure)
                return self.finished
            deferred = Deferred()
            deferred.callback(self.verifier.verification_completed())
            return deferred
        else:
            self.verifier.task_timeout(self.subtask_id)
        return None

    def __crop_rendered(self, result):
        self.verifier.verify_with_crop(result)

    def __crop_render_failure(self, error):
        logger.warning("Error %s", error)
        self.finished.errback(error)

    def failure(self, error):
        logger.info("Verification Task failure %s", error)

    def start_verification(self, results):
        self.verifier.make_verdict(results)
        self.finished.callback(self.verifier.verification_completed())

    def get_results(self):
        return self.verifier.verification_completed()

    # Currently golem protocol does not allow for partial verification,
    # therefore we have to wait for any ongoing verification.
    def stop(self, finished):
        self.verifier.stop()
        finished.cancel()
