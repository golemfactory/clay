from typing import NamedTuple, List, Dict, Callable, Any

SubtaskID = str
QueueID = str
TaskID = str

Host = str
Port = int


# TODO should be typed differently
class SubtaskData(NamedTuple):
    args: List[Any]
    kwargs: Dict[str, Any]
    function: Callable[..., Any]


class SubtaskDefinition(NamedTuple):
    subtask_id: SubtaskID
    queue_id: QueueID
    data: SubtaskData


class FinishComputations(NamedTuple):
    pass