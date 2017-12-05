import os
from PIL import Image

from mock import patch, Mock

from golem.core.common import is_linux
from golem.task.taskbase import Task
from golem.testutils import TempDirFixture, PEP8MixIn
from golem.tools.assertlogs import LogTestCase
from golem.verification.verificator import SubtaskVerificationState

from apps.rendering.task.verificator import RenderingVerificator, logger, FrameRenderingVerificator
from apps.rendering.task.renderingtaskstate import AdvanceRenderingVerificationOptions


class TestRenderingVerificator(TempDirFixture, LogTestCase, PEP8MixIn):
    PEP8_FILES = [
        'apps/rendering/task/verificator.py',
    ]

    def test_get_part_size(self):
        rv = RenderingVerificator()
        rv.res_x = 800
        rv.res_y = 600
        assert rv._get_part_size(dict()) == (800, 600)

    def test_verify(self):
        rv = RenderingVerificator()
        # Result us not a file
        assert rv.verify("Subtask1", dict(), ["file1"], Mock()) == \
               SubtaskVerificationState.WRONG_ANSWER

        rv.res_x = 80
        rv.res_y = 60
        rv.total_tasks = 30
        # No data
        assert rv.verify("Subtask1", {"start_task": 3}, [], Mock()) == \
                         SubtaskVerificationState.WRONG_ANSWER

        # Result is not an image
        assert rv.verify("Subtask1", {"start_task": 3}, ["file1"], Mock()) == \
               SubtaskVerificationState.WRONG_ANSWER

        img_path = os.path.join(self.path, "img1.png")
        img = Image.new("RGB", (80, 60))
        img.save(img_path)

        img_path2 = os.path.join(self.path, "img2.png")
        img = Image.new("RGB", (80, 60))
        img.save(img_path2)

        ver_dir = os.path.join(self.path, "ver_img")
        os.makedirs(ver_dir)
        img_path3 = os.path.join(ver_dir, "img3.png")
        img.save(img_path3)

        # Proper simple verification - just check if images have proper sizes
        assert rv.verify("Subtask1", {"start_task": 3},
                         [img_path, img_path2], Mock()) == \
               SubtaskVerificationState.VERIFIED


    def test_get_part_img_size(self):
        rv = RenderingVerificator()
        rv.res_x = 800
        rv.res_y = 600
        rv.total_tasks = 30
        assert rv._get_part_img_size({"start_task": 3}) == (0, 40, 800, 60)

        rv.total_tasks = 0
        with self.assertLogs(logger, level="WARNING"):
            assert rv._get_part_img_size({"start_task": 3}) == (0, 0, 0, 0)

        rv.total_tasks = 30
        with self.assertLogs(logger, level="WARNING"):
            assert rv._get_part_img_size({"start_task": 34}) == (0, 0, 0, 0)

        rv.total_tasks = 11
        rv.res_y = 211
        assert rv._get_part_img_size({"start_task": 5}) == (0, 76, 800, 95)


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
        assert frv._get_part_img_size(subtask_info) == (1, 1, 599, 199)
        frv.use_frames = False
        assert frv._get_part_img_size(subtask_info) == (0, 0, 600, 40)

