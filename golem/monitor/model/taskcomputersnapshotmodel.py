from .modelbase import BasicModel


class TaskComputerSnapshotModel(BasicModel):

    def __init__(self, meta_data, task_computer):
        super().__init__("TaskComputer", meta_data.cliid, meta_data.sessid)

        self.compute_task = task_computer.compute_tasks
        self.assigned_subtasks = list(task_computer.assigned_subtasks.keys())
