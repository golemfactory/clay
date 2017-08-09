from mock import Mock

from apps.core.task.verificator import SubtaskVerificationState
from apps.dummy.task.verificator import DummyTaskVerificator
from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase


class TestDummyTaskVerificator(TempDirFixture, LogTestCase):
    def test_check_files(self):
        # TODO here
        dv = DummyTaskVerificator()
        dv._check_files("SUBTASK1", {}, [], Mock())
        assert (dv.get_verification_state("SUBTASK1") == SubtaskVerificationState.WRONG_ANSWER)
        dv._check_files("SUBTASK2", {}, ["not existing"], Mock())
        assert (dv.get_verification_state("SUBTASK2") == SubtaskVerificationState.WRONG_ANSWER)
