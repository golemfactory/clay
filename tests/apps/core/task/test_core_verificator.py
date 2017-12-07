from mock import Mock

from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.verification.verificator import SubtaskVerificationState

from apps.core.task.verificator import CoreVerificator


class TestCoreVerificator(TempDirFixture, LogTestCase):

    def test_check_files(self):
        def callback(*args, **kwargs):
            pass

        cv = CoreVerificator(callback)
        cv._check_files(dict(), [])
        assert cv.state == SubtaskVerificationState.WRONG_ANSWER

        files = self.additional_dir_content([3])
        cv._check_files(dict(), files)
        assert cv.state ==  SubtaskVerificationState.VERIFIED

        files = self.additional_dir_content([3])
        cv._check_files(dict(), [files[0]])
        assert cv.state == SubtaskVerificationState.VERIFIED

        cv._check_files(dict(), ["not a file"])
        assert cv.state == SubtaskVerificationState.WRONG_ANSWER
