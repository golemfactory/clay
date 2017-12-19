from .modelbase import BasicModel


# pylint:disable=too-few-public-methods
class SubtaskFailedModel(BasicModel):

    # pylint:disable=too-many-arguments
    def __init__(self, cliid, sessid, hardware, performance_values, task_id,
                 subtask_id, reason):
        super().__init__('SubtaskFailed', cliid, sessid)
        self.hardware = hardware
        self.performance_values = performance_values
        self.task_id = task_id
        self.subtask_id = subtask_id
        self.reason = reason
