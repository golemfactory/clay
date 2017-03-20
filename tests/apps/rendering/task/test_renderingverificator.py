import os
from PIL import Image

from mock import patch, Mock

from golem.core.common import is_linux
from golem.task.taskbase import Task
from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase

from apps.core.task.verificator import SubtaskVerificationState
from apps.rendering.task.verificator import RenderingVerificator, logger, FrameRenderingVerificator
from apps.rendering.task.renderingtaskstate import AdvanceRenderingVerificationOptions


class TestRenderingVerificator(TempDirFixture, LogTestCase):
    def test_box_start(self):
        rv = RenderingVerificator()

        rv.verification_options = AdvanceRenderingVerificationOptions()
        rv.verification_options.box_size = (5, 5)
        sizes = [(24, 12, 44, 20), (0, 0, 800, 600), (10, 150, 12, 152)]
        for size in sizes:
            for i in range(20):
                x, y = rv._get_box_start(*size)
                assert size[0] <= x <= size[2]
                assert size[1] <= y <= size[3]

    def test_get_part_size(self):
        rv = RenderingVerificator()
        rv.res_x = 800
        rv.res_y = 600
        assert rv._get_part_size("Subtask1", dict()) == (800, 600)

    @patch("apps.rendering.task.verificator.LocalComputer")
    def test_verify(self, computer_mock):
        rv = RenderingVerificator()
        # No subtask info
        assert rv.verify("Subtask1", dict(), ["file1"], Mock()) == SubtaskVerificationState.UNKNOWN

        rv.res_x = 800
        rv.res_y = 600
        rv.total_tasks = 30
        # No data
        assert rv.verify("Subtask1", {"start_task": 3}, [], Mock()) == \
                         SubtaskVerificationState.WRONG_ANSWER

        # Result is not an image
        assert rv.verify("Subtask1", {"start_task": 3}, ["file1"], Mock()) == \
               SubtaskVerificationState.WRONG_ANSWER

        img_path = os.path.join(self.path, "img1.png")
        img = Image.new("RGB", (800, 600))
        img.save(img_path)

        img_path2 = os.path.join(self.path, "img2.png")
        img.save(img_path2)

        ver_dir = os.path.join(self.path, "ver_img")
        os.makedirs(ver_dir)
        img_path3 = os.path.join(ver_dir, "img3.png")
        img.save(img_path3)

        # Proper simple verification - just check if there's a image with right size in results
        assert rv.verify("Subtask1", {"start_task": 3}, [img_path, img_path2], Mock()) == \
               SubtaskVerificationState.VERIFIED

        # ADVANCE VERIFICATION

        rv.advanced_verification = True
        rv.verification_options = AdvanceRenderingVerificationOptions()
        rv.verification_options.type = "forAll"
        rv.verification_options.box_size = [5, 5]
        rv.tmp_dir = self.path
        rv.root_path = self.path

        # No image files in results
        computer_mock.return_value.tt.result.get.return_value = self.additional_dir_content([3])
        assert rv.verify("Subtask1", {"start_task": 3, "output_format": "png"},
                         [img_path], Mock()) == SubtaskVerificationState.WRONG_ANSWER

        # Properly verified
        adv_ver_res = [img_path3,  os.path.join(ver_dir, "cos.log")]
        computer_mock.return_value.tt.result.get.return_value = adv_ver_res
        assert rv.verify("Subtask1", {"start_task": 3, "output_format": "png",
                                      "node_id": "ONENODE"},
                         [img_path], Mock()) == SubtaskVerificationState.VERIFIED

        if is_linux() and os.geteuid() == 0:
            rv.tmp_dir = "/nonexisting"
            assert rv.verify("Subtask1", {"start_task": 3, "output_format": "png",
                                          "node_id": "ONENODE"},
                             [img_path], Mock()) == SubtaskVerificationState.UNKNOWN

    def test_get_part_img_size(self):
        rv = RenderingVerificator()
        rv.res_x = 800
        rv.res_y = 600
        rv.total_tasks = 30
        assert rv._get_part_img_size("Subtask1", None, {"start_task": 3}) == (0, 40, 800, 60)

        rv.total_tasks = 0
        with self.assertLogs(logger, level="WARNING"):
            assert rv._get_part_img_size("Subtask1", None, {"start_task": 3}) == (0, 0, 0, 0)

        rv.total_tasks = 30
        with self.assertLogs(logger, level="WARNING"):
            assert rv._get_part_img_size("Subtask1", None, {"start_task": 34}) == (0, 0, 0, 0)

        rv.total_tasks = 11
        rv.res_y = 211
        assert rv._get_part_img_size("Subtask1", None, {"start_task": 5}) == (0, 76, 800, 95)

    def test_choose_adv_ver_file(self):
        rv = RenderingVerificator()
        rv.verification_options = AdvanceRenderingVerificationOptions()
        rv.advanced_verification = False
        assert rv._choose_adv_ver_file(range(5), {"node_id": "nodeX"}) is None
        rv.advanced_verification = True
        rv.verification_options.type = "forFirst"
        assert rv._choose_adv_ver_file(range(5), {"node_id": "NodeX"}) in range(5)
        rv.verified_clients.append("NodeX")
        assert rv._choose_adv_ver_file(range(5), {"node_id": "NodeX"}) is None
        rv.verification_options.type = "forAll"
        assert rv._choose_adv_ver_file(range(5), {"node_id": "NodeX"}) in range(5)
        rv.verification_options.type = "random"
        rv.verification_options.probability = 1.0
        assert rv._choose_adv_ver_file(range(5), {"node_id": "NodeX"}) in range(5)
        rv.verification_options.probability = 0.0
        assert rv._choose_adv_ver_file(range(5), {"node_id": "NodeX"}) is None

    def test_error_in_change_scope(self):
        rv = RenderingVerificator()
        rv.tmp_dir = None
        subtask_info = {'start_task': 1, 'tmp_path': 'blabla'}
        with self.assertRaises(Exception):
            rv.change_scope("subtask_id", (0, 0), self.temp_file_name("tmpfile"), subtask_info)

    def test_box_render_error(self):
        rv = RenderingVerificator()
        with self.assertLogs(logger, level="WARNING") as l:
            rv._RenderingVerificator__box_render_error("some error")
            assert any("some error" in log for log in l.output)

    def test_run_task_with_errors(self):
        rv = RenderingVerificator()
        rv.root_path = self.path
        extra_data = {}

        class MockTask(Task):
            pass

        assert rv._run_task(extra_data, MockTask(Mock(), Mock())) is None


class TestFrameRenderingVerificator(TempDirFixture):
    def test_check_files(self):
        frv = FrameRenderingVerificator()
        frv.total_tasks = 20
        frv.use_frames = False
        frv._check_files("id1", {"frames": [3]}, [], Mock())
        assert frv.ver_states["id1"] == SubtaskVerificationState.WRONG_ANSWER

        frv.use_frames = True
        frv.frames = [3, 4, 5, 6]
        frv._check_files("id1", {"frames": [3]}, [], Mock())
        assert frv.ver_states["id1"] == SubtaskVerificationState.WRONG_ANSWER

        frv.total_tasks = 2
        frv._check_files("id1", {"frames": [3]}, [], Mock())
        assert frv.ver_states["id1"] == SubtaskVerificationState.WRONG_ANSWER

        frv._check_files("id1", {"frames": [3, 4]}, ["file1"], Mock())
        assert frv.ver_states["id1"] == SubtaskVerificationState.WRONG_ANSWER

        frv._check_files("id1", {"frames": [3, 4], "start_task": 1}, ["file1", "file2"], Mock())
        assert frv.ver_states["id1"] == SubtaskVerificationState.WRONG_ANSWER

    def test_get_part_img_size(self):
        frv = FrameRenderingVerificator()
        frv.res_x = 600
        frv.res_y = 800
        frv.use_frames = True
        frv.total_tasks = 20
        frv.frames = [5, 6, 7, 8, 9]
        subtask_info = {'start_task': 1, 'parts': 4}
        assert frv._get_part_img_size("sub1", None, subtask_info) == (1, 1, 599, 199)
        frv.use_frames = False
        assert frv._get_part_img_size("sub1", None, subtask_info) == (0, 0, 600, 40)

