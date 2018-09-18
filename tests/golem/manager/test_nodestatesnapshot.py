from unittest import TestCase

from golem.manager.nodestatesnapshot import ComputingSubtaskStateSnapshot, \
                                            LocalTaskStateSnapshot


class TestComputingSubtaskStateSnapshot(TestCase):
    def test_state(self):
        # given
        state_snapshot_dict = {
            'subtask_id': "some-subtask_id",
            'progress': 0.0,
            'seconds_to_timeout': 0.0,
            'running_time_seconds': 0.0,
            'outfilebasename': "Test Task",
            'output_format': "PNG",
            'scene_file': "/golem/resources/cube.blend",
            'frames': [1],
            'start_task': 1,
            'end_task': 1,
            'total_tasks': 1,
            'some_unused_field': 1234,
        }

        # when
        tcss = ComputingSubtaskStateSnapshot(**state_snapshot_dict)

        # then
        state_snapshot_dict['scene_file'] = "cube.blend"
        del state_snapshot_dict['some_unused_field']
        assert tcss.__dict__ == state_snapshot_dict


class TestLocalTaskStateSnapshot(TestCase):
    def test_state(self):
        ltss = LocalTaskStateSnapshot("xyz", 1000, 200, 0.8, "very big task")
        assert isinstance(ltss, LocalTaskStateSnapshot)
        assert ltss.task_id == "xyz"
        assert ltss.total_tasks == 1000
        assert ltss.active_tasks == 200
        assert ltss.progress == 0.8
        assert ltss.task_short_desc == "very big task"

        assert ltss.get_task_id() == "xyz"
        assert ltss.get_total_tasks() == 1000
        assert ltss.get_active_tasks() == 200
        assert ltss.get_progress() == 0.8
        assert ltss.get_task_short_desc() == "very big task"
