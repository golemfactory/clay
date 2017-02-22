from unittest import TestCase

from apps.blender.task.verificator import BlenderVerificator


class TestBlenderVerificator(TestCase):
    def test_get_part_size_from_subtask_number(self):
        bv = BlenderVerificator()

        bv.res_y = 600
        bv.total_tasks = 20
        assert bv._get_part_size_from_subtask_number(3) == 30
        bv.total_tasks = 13
        assert bv._get_part_size_from_subtask_number(2) == 47
        assert bv._get_part_size_from_subtask_number(3) == 46
        assert bv._get_part_size_from_subtask_number(13) == 46
