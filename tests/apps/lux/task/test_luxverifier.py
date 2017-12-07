import os
from mock import patch, Mock

from golem.testutils import PEP8MixIn, TempDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.verification.verifier import SubtaskVerificationState

from apps.lux.task.verifier import LuxRenderVerifier, logger
from apps.rendering.task.renderingtaskstate import AdvanceRenderingVerificationOptions




class TestLuxRenderVerifier(TempDirFixture, LogTestCase, PEP8MixIn):
    PEP8_FILES = [
        # 'apps/lux/task/verifier.py',
    ]

    # @patch("apps.lux.task.verifier.LocalComputer")
    # def test_merge_flm_files_failure(self, mock_lc):
    #     mock_lc.return_value.tt = None
    #     lrv = LuxRenderVerifier(AdvanceRenderingVerificationOptions)
    #     lrv.tmp_dir = self.path
    #     assert not lrv.merge_flm_files("flm_file", Mock(), "flm_output")
    #     mock_lc.return_value.tt = Mock()
    #     lrv.verification_error = True
    #     assert not lrv.merge_flm_files("flm_file", Mock(), "flm_output")
    #     lrv.verification_error = False
    #     mock_lc.return_value.tt.result = {'data': self.additional_dir_content([3])}
    #     assert not lrv.merge_flm_files("flm_file", Mock(), "flm_output")
    #     flm_file = os.path.join(self.path, "bla.flm")
    #     open(flm_file, 'w').close()
    #     mock_lc.return_value.tt.result = {'data': self.additional_dir_content([1]) + [flm_file]}
    #     assert not lrv.merge_flm_files("flm_file", Mock(), "flm_output")
    #     stderr_file = os.path.join(self.path, "stderr.log")
    #     mock_lc.return_value.tt.result = {'data': [flm_file, stderr_file]}
    #     assert not lrv.merge_flm_files("flm_file", Mock(), "flm_output")
    #     open(stderr_file, 'w').close()
    #     assert lrv.merge_flm_files("flm_file", Mock(), "flm_output")
    #     with open(stderr_file, 'w') as f:
    #         f.write("ERROR at merging files")
    #
    #     assert not lrv.merge_flm_files("flm_file", Mock(), "flm_output")

    # def test_flm_verify_failure(self):
    #     lrv = LuxRenderVerifier(AdvanceRenderingVerificationOptions)
    #     with self.assertLogs(logger, level="INFO"):
    #         lrv._LuxRenderVerifier__verify_flm_failure("Error in something")
    #     assert lrv.verification_error
    #

