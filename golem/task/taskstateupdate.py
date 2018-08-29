import threading
from typing import Dict, Optional, Any

import enforce
from golem_messages import message


@enforce.runtime_validation(group="taskstateupdate")
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
    def from_dict(d: Dict[str, Any]):
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


@enforce.runtime_validation(group="taskstateupdate")
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
    def from_dict(d: Dict[str, Any]):
        return StateUpdateData(
            info=StateUpdateInfo.from_dict(d["info"]),
            data=d["data"])


# this is a class and not a namedtuple because we need mutability
# but, in the future (after python 3.7), it probably should be changed
# to dataclass
@enforce.runtime_validation(group="taskstateupdate")
class StateUpdateResponse():
    def __init__(self, event: threading.Event, data: Optional[Dict]):
        if not isinstance(event, threading.Event):
            raise TypeError("Event should be of type threading.Event."
                            f"instead got {event}")
        self.event = event
        self.data = data


@enforce.runtime_validation(group="taskstateupdate")
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


enforce.config({'groups': {'set': {'taskstateupdate': True}}})
