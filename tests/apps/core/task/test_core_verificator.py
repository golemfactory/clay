from unittest import TestCase

from apps.core.task.verificator import CoreVerificator, SubtaskVerificationState


class TestCoreVerificator(TestCase):
    def test_is_verified(self):
        cv = CoreVerificator()
        assert not cv.is_verified("SUBTASKWHENNOSUBTASKKNOWN")
        cv.ver_states["SUBTASK UNKOWN"] = SubtaskVerificationState.UNKNOWN
        cv.ver_states["SUBTASK WAITING"] = SubtaskVerificationState.WAITING
        cv.ver_states["SUBTASK PARTIALLY VERIFIED"] = SubtaskVerificationState.PARTIALLY_VERIFIED
        cv.ver_states["SUBTASK VERIFIED"] = SubtaskVerificationState.VERIFIED
        cv.ver_states["SUBTASK WRONG_ANSWER"] = SubtaskVerificationState.WRONG_ANSWER
        cv.ver_states["another_verified"] = SubtaskVerificationState.VERIFIED
        assert not cv.is_verified("COMPLETELY UNKNOWN")
        assert not cv.is_verified("SUBTASK UNKNOWN")
        assert not cv.is_verified("SUBTASK PARTIALLY VERIFIED")
        assert not cv.