from typing import NamedTuple, Dict

StateUpdateId = str  # probably not really Pythonic

# class TaskInfo(NamedTuple):
#     task_id: str
#     subtask_id: str
#
#
# class StateUpdateCall(NamedTuple):
#     task_info: TaskInfo
#     state_update_id: StateUpdateId
#     data: Dict
#
#
# class StateUpdateReturn(NamedTuple):
#     task_info: TaskInfo
#     state_update_id: StateUpdateId
#     data: Dict

class TaskInfo():
    def __init__(self, task_id: str, subtask_id: str):
        self.task_id = task_id
        self.subtask_id = subtask_id


class StateUpdateData():
    def __init__(self, task_info: TaskInfo, state_update_id: StateUpdateId, data: Dict):
        self.task_info = task_info
        self.state_update_id = state_update_id
        self.data = data