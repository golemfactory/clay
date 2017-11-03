from datetime import datetime
from unittest import TestCase

from golem.manager.nodestatesnapshot import TaskChunkStateSnapshot, \
                                            LocalTaskStateSnapshot


class TestTaskChunkStateSnapshot(TestCase):
    def test_state(self):
        tcss = TaskChunkStateSnapshot("xxyyzz", 1032, 240, 0.8, "some work")
        assert isinstance(tcss, TaskChunkStateSnapshot)
        assert tcss.chunk_id == "xxyyzz"
        assert tcss.cpu_power == 1032
        assert tcss.est_time_left == 240
        assert tcss.progress == 0.8
        assert tcss.chunk_short_desc == "some work"

        assert tcss.get_chunk_id() == "xxyyzz"
        assert tcss.get_cpu_power() == 1032
        assert tcss.get_estimated_time_left() == 240
        assert tcss.get_progress() == 0.8
        assert tcss.get_chunk_short_descr() == "some work"


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
