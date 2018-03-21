import os
from unittest import mock

from apps.blender.task.verifier import BlenderVerifier, logger
from apps.blender.task.blendercropper import CropContext

from golem.testutils import PEP8MixIn, TempDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.tools.ci import ci_skip


class TestBlenderVerifier(LogTestCase, PEP8MixIn, TempDirFixture):
    PEP8_FILES = ["apps/blender/task/verifier.py"]

    def test_get_part_size_from_subtask_number(self):
        bv = BlenderVerifier(lambda: None)
        subtask_info = {
            "res_y": 600,
            "total_tasks": 20,
            "start_task": 3,
        }
        assert bv._get_part_size_from_subtask_number(subtask_info) == 30
        subtask_info["total_tasks"] = 13
        subtask_info["start_task"] = 2
        assert bv._get_part_size_from_subtask_number(subtask_info) == 47
        subtask_info["start_task"] = 3
        assert bv._get_part_size_from_subtask_number(subtask_info) == 46
        subtask_info["start_task"] = 13
        assert bv._get_part_size_from_subtask_number(subtask_info) == 46

    def test_get_part_size(self):
        bv = BlenderVerifier(lambda: None)
        subtask_info = {
            "use_frames": False,
            "res_x": 800,
            "res_y": 600,
            "total_tasks": 20,
            "start_task": 3,
        }
        assert bv._get_part_size(subtask_info) == (800, 30)
        subtask_info["use_frames"] = True
        subtask_info["all_frames"] = list(range(40))
        assert bv._get_part_size(subtask_info) == (800, 600)
        subtask_info["all_frames"] = list(range(10))
        assert bv._get_part_size(subtask_info) == (800, 300)

    def test_crop_render_failure(self):
        bv = BlenderVerifier(lambda: None)
        bv.failure = lambda: None
        with self.assertLogs(logger, level="WARNING") as logs:
            bv._crop_render_failure("There was a problem")
        assert any("WARNING:apps.blender:Crop for verification render failure"
                   " 'There was a problem'"
                   in log for log in logs.output)

    @ci_skip
    @mock.patch('golem.docker.job.DockerJob.start')
    @mock.patch('golem.docker.job.DockerJob.wait')
    def test_crop_rendered(self, wait_mock, start_mock):
        bv = BlenderVerifier(lambda: None)
        verify_ctx = CropContext({'position': [[0.2, 0.4, 0.2, 0.4],
                                               [[75, 34]], 0.05],
                                  'paths': self.tempdir},
                                 mock.MagicMock(), mock.MagicMock(),
                                 mock.MagicMock())
        crop_path = os.path.join(self.tempdir, str(0))
        bv.current_results_file = os.path.join(self.tempdir, "none.png")
        open(bv.current_results_file, mode='a').close()
        if not os.path.exists(crop_path):
            os.mkdir(crop_path)
        output_dir = os.path.join(crop_path, "output")
        if not os.path.exists(output_dir):
            os.mkdir(output_dir)
        f = open(os.path.join(output_dir, "result.txt"), mode='a')
        f.write("{")
        f.write("\"MSE_canny\": 2032.03125,")
        f.write("\"MSE_normal\": 1.171875,")
        f.write("\"MSE_wavelet\": 5080.765625,")
        f.write("\"SSIM_canny\": 0.9377418556022814,")
        f.write("\"SSIM_normal\": 0.9948028194990917,")
        f.write("\"SSIM_wavelet\": 0.7995332835184454,")
        f.write("\"crop_resolution\": \"8x8\",")
        f.write("\"imgCorr\": 0.7342643964262355")
        f.write("}")
        f.close()
        with self.assertLogs(logger, level="INFO") as logs:
            bv._crop_rendered({"data": ["def"]}, 2913, verify_ctx, 0)
        assert any("Crop for verification rendered"
                   in log for log in logs.output)
        assert any("2913" in log for log in logs.output)
        assert any("def" in log for log in logs.output)
