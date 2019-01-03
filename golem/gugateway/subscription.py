from collections import Counter
from enum import auto, Enum, unique
import json
from typing import Union


@unique
class TaskType(Enum):
    Blender = auto()
    Transcoding = auto()


class TaskStatus(Enum):
    requested = auto()
    succeeded = auto()
    failed = auto()
    timedout = auto()


class Subscription(object):
    """ Golem Unlimited Gateway subscription"""

    def __init__(self):
        self.task_types: set[TaskType] = set()
        self.stats: Counter = Counter()

    def toggle_task_type(self, task_type: Union[TaskType, str]) -> str:
        if isinstance(task_type, str):
            try:
                task_type = TaskType[task_type]
            except KeyError:
                known_task_types = ', '.join(TaskType.__members__)
                return f'task type {task_type} not known. Here is a list of ' \
                       f'supported task types: {known_task_types}'

        if task_type in self.task_types:
            self.task_types.remove(task_type)
        else:
            self.task_types.add(task_type)

    def increment_stat(self, status: Union[TaskStatus, str]) -> str:
        if isinstance(status, str):
            try:
                status = TaskStatus[status]
            except KeyError:
                known_stats = ', '.join(TaskStatus.__members__)
                return f'unknown task status {status}. Here is a list of ' \
                       f'supported task statuses: {known_stats}'
        self.stats.update([status.name])

    def to_json(self) -> json:
        return json.dumps({
            'taskTypes': list(map(lambda x: x.name, self.task_types)),
            'taskStats': dict(self.stats)
        })
