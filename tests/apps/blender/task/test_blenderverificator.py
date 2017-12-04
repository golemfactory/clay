from unittest import TestCase

from apps.blender.task.verificator import BlenderVerificator

from apps.core.task.verificator import SubtaskVerificationState

import os

from apps.rendering.resources.ImgVerificator import ImgStatistics, \
    ImgVerificator

from apps.core.task.verificator import \
    SubtaskVerificationState as VerificationState
from apps.rendering.resources.imgrepr import PILImgRepr

from golem.tools.assertlogs import LogTestCase
from golem import testutils
from golem.core.common import get_golem_path

from mock import Mock, MagicMock, patch


class TestBlenderVerificator(LogTestCase, testutils.PEP8MixIn):
    PEP8_FILES = ['apps/blender/task/verificator.py']

    def test_get_part_size_from_subtask_number(self):
        bv = BlenderVerificator()

        bv.res_y = 600
        bv.total_tasks = 20
        assert bv._get_part_size_from_subtask_number(3) == 30
        bv.total_tasks = 13
        assert bv._get_part_size_from_subtask_number(2) == 47
        assert bv._get_part_size_from_subtask_number(3) == 46
        assert bv._get_part_size_from_subtask_number(13) == 46

    def test_get_part_size(self):
        bv = BlenderVerificator()
        bv.use_frames = False
        bv.res_x = 800
        bv.res_y = 600
        bv.total_tasks = 20
        assert bv._get_part_size({"start_task": 3}) == (800, 30)
        bv.use_frames = True
        bv.frames = list(range(40))
        assert bv._get_part_size({"start_task": 3}) == (800, 600)
        bv.frames = list(range(10))
        assert bv._get_part_size({"start_task": 3}) == (800, 300)
