from collections import Counter
from enum import auto, Enum
from pydispatch import dispatcher
from typing import Union, Dict, List, Optional

from golem.client import Client
from golem.clientconfigdescriptor import ClientConfigDescriptor


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
                 'resource_size', 'estimated_memory', 'max_price',
                 'min_version']

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


class Subtask(object):
    """ Golem subtask representation for GU gateway"""

    __slots__ = ['task_id', 'subtask_id', 'price', 'deadline',
                 'docker_images', 'extra_data']

    def __init__(self, **kwargs):
        self.price = int(kwargs['price'])
        ctd = kwargs['ctd']
        self.task_id = ctd['task_id']
        self.subtask_id = ctd['subtask_id']
        self.deadline: int = int(ctd['deadline'])
        self.docker_images = ctd['docker_images']
        self.extra_data: dict = ctd['extra_data']
        self.extra_data['src_code'] = ctd['src_code']

    def to_json_dict(self) -> dict:
        return {
            'taskId': self.task_id,
            'subtaskId': self.subtask_id,
            'price': self.price,
            'deadline': self.deadline,
            'docker_images': self.docker_images,
            'extra_data': self.extra_data
        }


# TODO: assign uuid for download
class Resource(object):

    __slots__ = ['task_id', 'subtask_id', 'path']

    def __init__(self, **kwargs):
        self.task_id = kwargs['task_id']
        self.subtask_id = kwargs['subtask_id']
        self.path = kwargs['path']

    def to_json_dict(self) -> dict:
        return {
            'taskId': self.task_id,
            'subtaskId': self.subtask_id,
            'path': self.path,
        }


# TODO
class SubtaskVerification(object):

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def to_json_dict(self) -> dict:
        return self.__dict__


class Event(object):
    """Events: task, subtask, resource and subtask verification result"""

    __slots__ = ['event_id', 'task', 'subtask', 'resource',
                 'subtask_verification']

    def __init__(self, event_id: int, **kwargs):

        self.event_id = event_id
        self.task: Optional[Task] = kwargs.get('task')
        self.subtask: Optional[Subtask] = kwargs.get('subtask')
        self.resource = kwargs.get('resource')
        self.subtask_verification = kwargs.get('subtask_verification')

    def to_json_dict(self) -> dict:
        return {
            'eventId': self.event_id,
            'task': self.task and self.task.to_json_dict(),
            'subtask': self.subtask and self.subtask.to_json_dict(),
            'resource': self.resource and self.resource.to_json_dict(),
            'subtaskVerification':
                self.subtask_verification
                and self.subtask_verification.to_json_dict()
        }


class Subscription(object):
    """ Golem Unlimited Gateway subscription"""

    def __init__(self, task_type: TaskType, request_json: dict):
        self.task_type: TaskType = task_type
        self.name = request_json.get('name', '')
        self.min_price = int(request_json['minPrice'])
        self.performance = float(request_json.get('performance', 0.0))
        self.max_cpu_cores = int(request_json['maxCpuCores'])
        self.max_memory_size = int(request_json['maxMemorySize'])
        self.max_disk_size = int(request_json['maxDiskSize'])
        self.stats: Counter = Counter()

        self.event_counter: int = 0
        # TODO: events TTL and cleanup
        self.events: Dict[str, Event] = dict()

    def _add_event(self, event_hash: str, **kwargs):
        event = Event(self.event_counter, **kwargs)
        self.event_counter += 1
        self.events[event_hash] = event

    def add_task_event(self, task_id: str, header: dict):
        if task_id in self.events:
            return

        self._add_event(task_id, task=Task(header))

    def request_task(self, golem_client: Client, task_id: str) -> None:
        self.set_config_to(golem_client.task_server.config_desc)
        golem_client.task_server.request_task(task_id, self.performance)
        dispatcher.connect(self.add_subtask_event, signal='golem.subtask')
        self.increment(TaskStatus.requested)

    def add_subtask_event(self, event='default', **kwargs) -> None:
        # print(f'sub event: {event}, {kwargs}')
        if event == 'started':  # TODO and kwargs['ctd']['task_id'] == task_id:
            subtask_id = kwargs['subtask_id']
            self._add_event(subtask_id, subtask=Subtask(**kwargs))
            dispatcher.disconnect(self.add_subtask_event,
                                  signal='golem.subtask')
            dispatcher.connect(self.add_resource_event,
                               signal='golem.resource')

    def add_resource_event(self, event='default', **kwargs) -> None:
        # print(f'event: {event}, kwargs: {kwargs}')
        subtask_id = kwargs['subtask_id']
        if event == 'collected':  # TODO and kwargs['subtask_id'] == subtask_id:
            self._add_event(f'rs-{subtask_id}', resource=Resource(**kwargs))
            dispatcher.disconnect(self.add_resource_event,
                                  signal='golem.resource')

    def increment(self, status: Union[TaskStatus, str]) -> None:
        if isinstance(status, str):
            status = TaskStatus.match(status)
        self.stats.update([status.name])

    def events_after(self, event_id: int) -> List[Event]:
        if event_id >= self.event_counter:
            raise KeyError(f'event id {event_id} should be less than '
                           f'{self.event_counter}')
        return [e for e in self.events.values() if e.event_id > event_id]

    def set_config_to(self, config_desc: ClientConfigDescriptor):
        config_desc.node_name = self.name
        config_desc.min_price = self.min_price
        config_desc.num_cores = self.max_cpu_cores
        config_desc.max_memory_size = self.max_memory_size
        config_desc.max_resource_size = self.max_disk_size

    def to_json_dict(self) -> dict:
        return {
            'taskType': self.task_type.name,
            'subscription': {
                'name': self.name,
                'minPrice': self.min_price,
                'performance': self.performance,
                'maxCpuCores': self.max_cpu_cores,
                'maxMemorySize': self.max_memory_size,
                'maxDiskSize': self.max_disk_size,
            },
            'taskStats': dict(self.stats)
        }

