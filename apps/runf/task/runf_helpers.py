from typing import NamedTuple, List, Dict, Optional

import enum

SubtaskID = str
QueueID = str
PickledObject = bytes
PickledCallable = bytes


class SubtaskData(NamedTuple):
    args: List[PickledObject]
    kwargs: Dict[str, PickledObject]
    function: PickledCallable
    TYPE: str = "SubmitNewTask"


class SubtaskDefinition(NamedTuple):
    subtask_id: SubtaskID
    queue_id: QueueID
    data: SubtaskData


class CheckSubtaskStatus(NamedTuple):
    subtask_id: SubtaskID
    TYPE: str = "CheckSubtaskStatus"


class FinishComputations(NamedTuple):
    TYPE: str = "FinishComputations"


class RunFSubtaskStatus(NamedTuple):
    """
        :status indicates status of subtask
        :result contains serialized output from function. it is present only
        if status == finished
        """

    class Status(enum.Enum):
        started = enum.auto()
        computing = enum.auto()
        timeout = enum.auto()
        finished = enum.auto()

    status: Status
    subtask_id: SubtaskID
    result: Optional[PickledObject]
