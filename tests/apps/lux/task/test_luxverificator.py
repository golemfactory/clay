import os
from mock import patch, Mock

from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase

from apps.core.task.verificator import SubtaskVerificationState
from apps.lux.task.verificator import LuxRenderVerificator, logger
from apps.rendering.task.renderingtaskstate import AdvanceRenderingVerificationOptions


class TestLuxRenderVerificator(TempDirFixture, LogTestCase):
    def test_check_files(self):
        lrv = LuxRenderVerificator(AdvanceRenderingVerificationOptions)
        lrv._check_files("SUBTASK1", {}, [], Mock())
        assert lrv.get_verification_state("SUBTASK1") == SubtaskVerificationState.WRONG_ANSWER
        lrv.advanced_verification = False
        lrv._check_files("SUBTASK2", {}, ["not existing"], Mock())
        assert lrv.get_verification_state("SUBTASK2") == SubtaskVerificationState.WRONG_ANSWER

    @patch("apps.lux.task.verificator.LocalComputer")
    def test_merge_flm_files_failure(self, mock_lc):
        mock_lc.return_value.tt = None
        lrv = LuxRenderVerificator(AdvanceRenderingVerificationOptions)
        lrv.tmp_dir = self.path
        assert not lrv.merge_flm_files("flm_file", Mock(), "flm_output")
        mock_lc.return_value.tt = Mock()
        lrv.verification_error = True
        assert not lrv.merge_flm_files("flm_file", Mock(), "flm_output")
        lrv.verification_error = False
        mock_lc.return_value.tt.result = {'data': self.additional_dir_content([3])}
        assert not lrv.merge_flm_files("flm_file", Mock(), "flm_output")
        flm_file = os.path.join(self.path, "bla.flm")
        open(flm_file, 'w').close()
        mock_lc.return_value.tt.result = {'data': self.additional_dir_content([1]) + [flm_file]}
        assert not lrv.merge_flm_files("flm_file", Mock(), "flm_output")
        stderr_file = os.path.join(self.path, "stderr.log")
        mock_lc.return_value.tt.result = {'data': [flm_file, stderr_file]}
        assert not lrv.merge_flm_files("flm_file", Mock(), "flm_output")
        open(stderr_file, 'w').close()
        assert lrv.merge_flm_files("flm_file", Mock(), "flm_output")
        with open(stderr_file, 'w') as f:
            f.write("ERROR at merging files")

        assert not lrv.merge_flm_files("flm_file", Mock(), "flm_output")

    def test_flm_verify_failure(self):
        lrv = LuxRenderVerificator(AdvanceRenderingVerificationOptions)
        with self.assertLogs(logger, level="INFO"):
            lrv._LuxRenderVerificator__verify_flm_failure("Error in something")
        assert lrv.verification_error
