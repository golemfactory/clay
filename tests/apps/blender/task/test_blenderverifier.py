from unittest import TestCase

from golem_verificator.blender.verifier import BlenderVerifier


class TestBlenderVerifier(TestCase):
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
