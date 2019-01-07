from collections import Counter
from enum import auto, Enum
import json
from typing import Union


class TaskType(Enum):
    Blender = auto()
    Transcoding = auto()

    @classmethod
    def match(cls, task_type: str):
        try:
            return TaskType[task_type]
        except KeyError as e:
            raise InvalidTaskType(str(e))


class InvalidTaskType(Exception):
    known_task_types = ', '.join(TaskType.__members__)

    def __str__(self):
        return f'task type {self.args[0]} not known. Here is a list' \
               f' of supported task types: {self.known_task_types}'


class TaskStatus(Enum):
    requested = auto()
    succeeded = auto()
    failed = auto()
    timedout = auto()

    @classmethod
    def match(cls, task_status: str):
        try:
            return TaskStatus[task_status]
        except KeyError as e:
            raise InvalidTaskStatus(str(e))


class InvalidTaskStatus(Exception):
    known_task_status = ', '.join(TaskType.__members__)

    def __str__(self):
        return f'task status {self.args[0]} not known. Here is a list' \
               f' of supported task types: {self.known_task_types}'


class Subscription(object):
    """ Golem Unlimited Gateway subscription"""

    def __init__(self, task_type: TaskType):
        self.task_type: TaskType = task_type
        self.stats: Counter = Counter()

    def increment(self, status: Union[TaskStatus, str]) -> str:
        if isinstance(status, str):
            status = TaskStatus.match(status)
        self.stats.update([status.name])

    def to_json(self) -> json:
        return json.dumps({
            'taskType': self.task_type.name,
            'taskStats': dict(self.stats)
        })
