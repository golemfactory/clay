from collections import Counter
from enum import auto, Enum
import json
from typing import Union, Dict, List


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
               f' of supported task statuses: {self.known_task_types}'


class Task(object):
    """ Golem task representation for GU gateway. Just header values"""

    __slots__ = ['task_id', 'deadline', 'subtask_timeout', 'subtasks_count',
                 'resource_size', 'estimated_memory', 'max_price', 'min_version'
                 ]

    def __init__(self, header: dict):
        self.task_id = header['task_id']
        self.deadline = header['deadline']
        self.subtask_timeout = header['subtask_timeout']
        self.subtasks_count = header['subtasks_count']
        self.resource_size = header['resource_size']
        self.estimated_memory = header['estimated_memory']
        self.max_price = header['max_price']
        self.min_version = header['min_version']

    def to_json_dict(self) -> dict:
        return {
            'taskId': self.task_id,
            'deadline': self.deadline,
            'subtaskTimeout': self.subtask_timeout,
            'subtasksCount': self.subtasks_count,
            'resourceSize': self.resource_size,
            'estimatedMemory': self.estimated_memory,
            'maxPrice': self.max_price,
            'minVersion': self.min_version
        }


class Event(object):
    """Three types of events: task, resources and subtask verification result"""

    __slots__ = ['event_id', 'task', 'resources', 'verification_res']

    def __init__(self, event_id: int, task: Task):
        self.event_id = event_id
        self.task: Task = task
        # TODO: resource and verification

    def to_json_dict(self) -> dict:
        return {
            'eventId': self.event_id,
            'task': self.task.to_json_dict()
        }


class Subscription(object):
    """ Golem Unlimited Gateway subscription"""

    def __init__(self, task_type: TaskType):
        self.task_type: TaskType = task_type
        self.stats: Counter = Counter()
        # self.tasks: Dict[str, Task] = dict()
        self.event_counter: int = 0
        # TODO: events TTL and cleanup
        self.events: Dict[str, Event] = dict()

    def _add_event(self, event_hash: str, event: Event):
        self.events[event_hash] = event
        self.event_counter += 1

    def add_task_event(self, task_id: str, header: dict):
        if task_id in self.events:
            return

        self._add_event(task_id, Event(self.event_counter, Task(header)))

    def increment(self, status: Union[TaskStatus, str]) -> str:
        if isinstance(status, str):
            status = TaskStatus.match(status)
        self.stats.update([status.name])

    def to_json_dict(self) -> dict:
        return {
            'taskType': self.task_type.name,
            'taskStats': dict(self.stats)
        }

    def to_json(self):
        return json.dumps(self.to_json_dict())

    def events_after(self, event_id: int) -> List[Event]:
        if event_id >= self.event_counter:
            raise KeyError(f'event id {event_id} should be less than '
                           f'{self.event_counter}')
        return [e for e in self.events.values() if e.event_id > event_id]

