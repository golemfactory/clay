import os
from PIL import Image

from mock import patch, Mock

from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase

from apps.core.task.verificator import SubtaskVerificationState
from apps.rendering.task.verificator import RenderingVerificator, logger
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
        assert rv.verify("Subtask1", dict(), ["file1"]) == SubtaskVerificationState.UNKNOWN

        rv.res_x = 800
        rv.res_y = 600
        rv.total_tasks = 30
        assert rv.verify("Subtask1", {"start_task": 3}, []) == \
                         SubtaskVerificationState.WRONG_ANSWER

        assert rv.verify("Subtask1", {"start_task": 3}, ["file1"]) == \
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

        assert rv.verify("Subtask1", {"start_task": 3}, [img_path, img_path2]) == \
               SubtaskVerificationState.VERIFIED

        rv.task_ref = Mock()
        rv.advance_verification = True
        rv.verification_options = AdvanceRenderingVerificationOptions()
        rv.verification_options.type = "forAll"
        rv.verification_options.box_size = [5, 5]
        rv.tmp_dir = self.path
        rv.root_path = self.path

        computer_mock.return_value.tt.result.get.return_value = self.additional_dir_content([3])
        assert rv.verify("Subtask1", {"start_task": 3, "output_format": "png"},
                         [img_path]) == SubtaskVerificationState.WRONG_ANSWER

        adv_ver_res = [img_path3,  os.path.join(ver_dir, "cos.log")]
        computer_mock.return_value.tt.result.get.return_value = adv_ver_res
        assert rv.verify("Subtask1", {"start_task": 3, "output_format": "png",
                                      "node_id": "ONENODE"},
                         [img_path]) == SubtaskVerificationState.VERIFIED


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

