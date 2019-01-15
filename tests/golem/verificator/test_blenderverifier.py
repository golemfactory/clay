import os
from unittest import mock

from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.verificator.blender_verifier import BlenderVerifier, logger
from golem.verificator.common.ci import ci_skip


class TestBlenderVerifier(LogTestCase, TempDirFixture):

    def test_get_part_size_from_subtask_number(self):
        subtask_info = {
            "resolution": [800, 600],
            "total_tasks": 20,
            "start_task": 3,
        }

        verification_data = {}
        verification_data['subtask_info'] = subtask_info
        verification_data['results'] = []
        verification_data['reference_data'] = []
        verification_data['resources'] = []

        blender_verifier = BlenderVerifier(verification_data,
                             cropper_cls=mock.Mock(),
                             docker_task_cls=mock.Mock())
        assert blender_verifier._get_part_size_from_subtask_number(subtask_info) == 30
        subtask_info["total_tasks"] = 13
        subtask_info["start_task"] = 2
        assert blender_verifier._get_part_size_from_subtask_number(subtask_info) == 47
        subtask_info["start_task"] = 3
        assert blender_verifier._get_part_size_from_subtask_number(subtask_info) == 46
        subtask_info["start_task"] = 13
        assert blender_verifier._get_part_size_from_subtask_number(subtask_info) == 46

    def test_get_part_size(self):

        crops = [
            {
                "outfilebasename": 'test',
                "borders_x": [0, 1],
                "borders_y": [0.05, 1]
            }
        ]
        subtask_info = {
            "subtask_id": "deadbeef",
            "use_frames": False,
            "resolution": [800, 600],
            "total_tasks": 20,
            "start_task": 3,
            "crops": crops
        }

        verification_data = {}
        verification_data['subtask_info'] = subtask_info
        verification_data['results'] = []
        verification_data['reference_data'] = []
        verification_data['resources'] = []

        blender_verifier = BlenderVerifier(verification_data,
                             cropper_cls=mock.Mock(),
                             docker_task_cls=mock.Mock())
        assert blender_verifier._get_part_size(subtask_info) == (800, 30)
        subtask_info["use_frames"] = True
        subtask_info["all_frames"] = list(range(40))
        subtask_info["crops"][0]['borders_x'] = [0, 1]
        subtask_info["crops"][0]['borders_y'] = [0, 1]
        assert blender_verifier._get_part_size(subtask_info) == (800, 600)
        subtask_info["all_frames"] = list(range(10))
        subtask_info["crops"][0]['borders_x'] = [0, 1]
        subtask_info["crops"][0]['borders_y'] = [0.5, 1]
        assert blender_verifier._get_part_size(subtask_info) == (800, 300)

    def test_crop_render_failure(self):
        verification_data = {}
        verification_data['subtask_info'] = {}
        verification_data['results'] = []
        verification_data['reference_data'] = []
        verification_data['resources'] = []

        blender_verifier = BlenderVerifier(verification_data,
                             cropper_cls=mock.Mock(),
                             docker_task_cls=mock.Mock())
        blender_verifier.failure = lambda: None

        with self.assertLogs(logger, level="WARNING") as logs:
            blender_verifier._crop_render_failure("There was a problem")
        assert any("WARNING:apps.blender:Crop render for verification failure"
                   " 'There was a problem'"
                   in log for log in logs.output)

    @ci_skip
    def test_crop_rendered(self):
        crop_path = os.path.join(self.tempdir, str(0))

        verification_data = {}
        verification_data['subtask_info'] = {'subtask_id': 'deadbeef'}
        verification_data['results'] = []
        verification_data['reference_data'] = []
        verification_data['resources'] = []

        reference_generator = mock.MagicMock()
        reference_generator.crop_counter = 3

        docker_task_thread = mock.Mock()
        docker_task_thread.return_value.output_dir_path = os.path.join(
            self.tempdir, 'output')
        docker_task_thread.specify_dir_mapping.return_value = \
            mock.Mock(resources=crop_path, temporary=self.tempdir)

        bv = BlenderVerifier(verification_data,
                             cropper_cls=reference_generator,
                             docker_task_cls=docker_task_thread)
        bv.current_results_files = [os.path.join(self.tempdir, "none.png")]
        open(bv.current_results_files[0], mode='a').close()
        if not os.path.exists(crop_path):
            os.mkdir(crop_path)
        output_dir = os.path.join(crop_path, "output")
        if not os.path.exists(output_dir):
            os.mkdir(output_dir)
        f = open(os.path.join(output_dir, "result_0.txt"), mode='a')
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
        verification_context = mock.MagicMock()
        verification_context.get_crop_path = mock.MagicMock(return_value="0")
        crop = mock.Mock()
        crop.get_relative_top_left = mock.Mock(return_value=(3,5))
        verification_context.get_crop_with_id = mock.Mock(return_value=crop)
        with self.assertLogs(logger, level="INFO") as logs:
            bv._crop_rendered(({"data": ["def"]}, 2913, verification_context, 0))
        assert any("rendered for verification"
                   in log for log in logs.output)
        assert any("2913" in log for log in logs.output)

