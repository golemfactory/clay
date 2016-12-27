from unittest import TestCase

from golem.task.taskstate import SubtaskState, SubtaskStatus

from gui.controller.previewcontroller import subtasks_priority


class TestPriorites(TestCase):
    def test_subtask_priority(self):
        s_rst = SubtaskState()
        s_rst.subtask_status = SubtaskStatus.restarted
        s_fil = SubtaskState()
        s_fil.subtask_status = SubtaskStatus.failure
        s_rsd = SubtaskState()
        s_rsd.subtask_status = SubtaskStatus.resent
        s_fin = SubtaskState()
        s_fin.subtask_status = SubtaskStatus.finished
        s_sta = SubtaskState()
        s_sta.subtask_status = SubtaskStatus.starting
        s_wai = SubtaskState()
        s_wai.subtask_status = SubtaskStatus.waiting
        assert subtasks_priority(s_rst) > subtasks_priority(s_fin)
        assert subtasks_priority(s_fil) > subtasks_priority(s_fin)
        assert subtasks_priority(s_rsd) > subtasks_priority(s_fin)
        assert subtasks_priority(s_fin) > subtasks_priority(s_sta)
        assert subtasks_priority(s_fin) > subtasks_priority(s_wai)