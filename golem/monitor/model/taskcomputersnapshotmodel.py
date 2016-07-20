from modelbase import BasicModel


class TaskComputerSnapshotModel(BasicModel):

    def __init__(self, waiting_for_task, counting_task, task_requested, compute_task, assigned_subtasks):
        super(TaskComputerSnapshotModel, self).__init__("TaskComputer")

        self.waiting_for_task = waiting_for_task
        self.counting_task = counting_task
        self.task_requested = task_requested
        self.compute_task = compute_task
        self.assigned_subtasks = assigned_subtasks

