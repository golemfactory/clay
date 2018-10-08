import logging
from threading import Lock
from typing import Optional, Any
from twisted.python.failure import Failure
from twisted.internet.defer import Deferred, DeferredList
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
        self.already_called = False
        self.lock = Lock()
        self.default_crops_number = 3
        self.__crop_jobs = DeferredList(
            [Deferred() for _ in
             range(self.default_crops_number)],
            fireOnOneErrback=True, consumeErrors=True)

    def start(self, verifier_class) -> Optional[Deferred]:
        self.verifier = verifier_class(self.kwargs)
        self.finished = Deferred()
        if deadline_to_timeout(self.deadline) > 0:
            try:
                if self.verifier.simple_verification(self.kwargs):
                    crop_jobs = self.reference_generator.render_crops(
                        self.kwargs['resources'],
                        self.kwargs["subtask_info"],
                        self.default_crops_number)
                    for d in crop_jobs:
                        d.addCallback(self.__crop_rendered)
                    self.__crop_jobs = DeferredList(
                        crop_jobs,
                        fireOnOneErrback=True,
                        consumeErrors=True)
                    self.__crop_jobs.addCallback(
                        self.start_verification)
                    self.__crop_jobs.addErrback(self.failure)
                else:
                    self.__call_if_not_called(
                        False,
                        self.verifier.verification_completed())
            except Exception as e: # pylint: disable=broad-except
                logger.warning("Exception in verification %s", e)
                self.__call_if_not_called(
                    False,
                    self.verifier.verification_completed())

        else:
            self.verifier.task_timeout(self.subtask_id)
        return self.finished

    def __crop_rendered(self, result):
        try:
            self.verifier.verify_with_crop(result)
            return True
        except Exception as e: # pylint: disable=broad-except
            logger.warning("__crop_rendered %s", e)
            return Failure(e)

    def failure(self, error):
        logger.info("Verification Task failure %s", error)
        self.__call_if_not_called(False, error)

    def start_verification(self, results):
        verdict = self.verifier.make_verdict(results)
        self.__call_if_not_called(verdict,
                                  self.verifier.verification_completed())

    def get_results(self):
        return self.verifier.verification_completed()

    def __call_if_not_called(self, callback, args):
        with self.lock:
            if self.already_called is False:
                self.already_called = True
                if callback is True:
                    self.finished.callback(args)
                else:
                    self.finished.errback(args)

    # Currently golem protocol does not allow for partial verification,
    # therefore we have to wait for any ongoing verification.
    def stop(self):
        self.__crop_jobs.cancel()
        self.finished.cancel()
        self.already_called = False
