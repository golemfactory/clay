from modelbase import BasicModel


class TaskComputerSnapshotModel(BasicModel):

    def __init__(self, meta_data, task_computer):
        super(TaskComputerSnapshotModel, self).__init__("TaskComputer", meta_data.cliid, meta_data.sessid)

        self.waiting_for_task = task_computer.waiting_for_task
        self.counting_task = task_computer.counting_task
        self.task_requested = task_computer.task_requested
        self.compute_task = task_computer.compute_tasks
        self.assigned_subtasks = task_computer.assigned_subtasks.keys()
