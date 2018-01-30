import os
import mock

from golem.core.common import timeout_to_deadline

from apps.blender.task.verifier import BlenderVerifier, logger,\
    VerificationContext

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
        verify_ctx = VerificationContext([[75, 34]], 0, self.tempdir)
        crop_path = os.path.join(self.tempdir, str(0))
        bv.current_results_file = os.path.join(self.tempdir, "none.png")
        if not os.path.exists(crop_path):
            os.mkdir(crop_path)
        with self.assertLogs(logger, level="INFO") as logs:
            bv._crop_rendered({"data": ["def"]}, 2913, verify_ctx)
        assert any("Crop for verification rendered"
                   in log for log in logs.output)
        assert any("2913" in log for log in logs.output)
        assert any("def" in log for log in logs.output)


    def test_generate_ctd(self):
        bv = BlenderVerifier(lambda: None)
        old_script = "print(str(2 + 3))"
        ctd = {"extra_data": {"outfilebasename": "mytask",
                              "script_src": old_script,
                              "new_arg": "def"},
               "deadline": timeout_to_deadline(1200)}

        old_deadline = ctd["deadline"]
        subtask_info = {"ctd": ctd,
                        "deadline": timeout_to_deadline(1200),
                        'new_arg': "abc",
                        "outfilebasename": "mytask",
                        'subtask_timeout': 700}
        new_script = "print('hello world!)"
        new_ctd = bv._generate_ctd(subtask_info, new_script)

        assert ctd['extra_data']['script_src'] == old_script
        assert new_ctd['extra_data']['script_src'] == new_script

        assert ctd['extra_data']['new_arg'] == "def"
        assert new_ctd['extra_data']['new_arg'] == "def"

        assert ctd['extra_data']['outfilebasename'] == "mytask"
        assert new_ctd['extra_data']['outfilebasename'] == "ref_mytask"

        assert ctd['deadline'] == old_deadline
        assert new_ctd['deadline'] != old_deadline
