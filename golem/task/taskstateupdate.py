import threading
from typing import Dict, Optional
from golem_messages import message


# StateUpdateId = str  # probably not really Pythonic
#
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


class StateUpdateInfo:
    def __init__(self, task_id: str, subtask_id: str, state_update_id: str):
        self.task_id = task_id
        self.subtask_id = subtask_id
        self.state_update_id = state_update_id

    @staticmethod
    def from_state_update_msg(msg: message.tasks.StateUpdate):
        return StateUpdateInfo.from_dict(
            {k: getattr(msg, k) for k in msg.__slots__}
        )

    @staticmethod
    def from_dict(d):
        return StateUpdateInfo(
            task_id=d["task_id"],
            subtask_id=d["subtask_id"],
            state_update_id=d["state_update_id"]
        )

    def __hash__(self):
        return hash("{}{}{}".format(self.task_id,
                                    self.subtask_id,
                                    self.state_update_id))

    def __eq__(self, other):
        return hash(self) == hash(other)


class StateUpdateData():
    def __init__(self, info: StateUpdateInfo, data: Dict):
        self.info = info
        self.data = data

    def to_dict(self):
        return {"task_id": self.info.task_id,
                "subtask_id": self.info.subtask_id,
                "state_update_id": self.info.state_update_id,
                "data": self.data}

    @staticmethod
    def from_dict(d: Dict):
        return StateUpdateData(
            info=StateUpdateInfo.from_dict(d["info"]),
            data=d["data"])


class StateUpdateResponse():
    def __init__(self, event: threading.Event, data: Optional[Dict]):
        self.event = event
        self.data = data


class StateUpdateProcessor():
    def __init__(self):
        self._msg_dict = {}

    def initialize(self, state_update: StateUpdateData):
        self._msg_dict[state_update.info] = StateUpdateResponse(
            event=threading.Event(),
            data=None
        )

    def get(self, state_update_info: StateUpdateInfo):
        return self._msg_dict[state_update_info]
