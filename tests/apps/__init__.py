
from golem.task.taskstate import SubtaskStatus


class TaskRestartMixin:
    def test_restart_subtask_new_state(self):
        task = self.task

        task.accept_client("node_ABC", 'ah')
        task.subtasks_given["ABC"] = {'status': SubtaskStatus.starting,
                                      'start_task': 3, "node_id": "node_ABC"}
        task.restart_subtask("ABC", new_state=SubtaskStatus.cancelled)
        assert task.subtasks_given["ABC"]["status"] == SubtaskStatus.restarted
