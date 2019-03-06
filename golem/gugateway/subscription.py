from collections import Counter
from enum import auto, Enum
from logging import Logger, getLogger
from pathlib import Path
from typing import Union, Dict, List, Optional

from golem_messages.datastructures.tasks import TaskHeader
from golem_messages.message.tasks import SubtaskResultsAccepted, \
    SubtaskResultsRejected
from pydispatch import dispatcher

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.task.taskserver import TaskServer

logger: Logger = getLogger(__name__)


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
        return f'task type {self.args[0]} not known. List' \
               f' of supported task types: {self.known_task_types}'


class SubtaskStatus(Enum):
    requested = auto()
    started = auto()
    cancelled = auto()
    succeeded = auto()
    failed = auto()
    timedout = auto()

    @classmethod
    def match(cls, task_status: str):
        try:
            return SubtaskStatus[task_status]
        except KeyError as e:
            raise InvalidSubtaskStatus(str(e))


class InvalidSubtaskStatus(Exception):
    known_statuses = ', '.join(SubtaskStatus.__members__)

    def __str__(self):
        if len(self.args[0].split()) == 1:
            return f'subtask status {self.args[0]} not known. List' \
                   f' of supported task statuses: {self.known_statuses}'

        return self.args[0]


class Task(object):
    """ Golem task representation for GU gateway. Just header values"""

    __slots__ = ['task_id', 'deadline', 'subtask_timeout', 'subtasks_count',
                 'resource_size', 'estimated_memory', 'max_price',
                 'min_version']

    def __init__(self, header: TaskHeader):
        self.task_id = header.task_id
        self.deadline = header.deadline
        self.subtask_timeout = header.subtask_timeout
        self.subtasks_count = header.subtasks_count
        self.resource_size = header.resource_size
        self.estimated_memory = header.estimated_memory
        self.max_price = header.max_price
        self.min_version = header.min_version

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
            'dockerImages': self.docker_images,
            'extraData': self.extra_data
        }


class Resource(object):
    """
    Golem task resource(s) identified by local path relative to root
    task manager folder.
    """

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


class SubtaskVerification(object):
    """ Golem subtask verification result"""

    __slots__ = ['task_id', 'subtask_id', 'verification_result', 'payment_ts',
                 'reason']

    def __init__(self, msg):
        self.task_id = msg.task_id
        self.subtask_id = msg.subtask_id
        if isinstance(msg, SubtaskResultsAccepted):
            self.verification_result = 'OK'
            self.payment_ts = msg.payment_ts
            self.reason = None
        elif isinstance(msg, SubtaskResultsRejected):
            self.verification_result = 'failed'
            self.payment_ts = None
            self.reason = msg.reason.value
        else:
            raise RuntimeError('unsupported msg type')

    def to_json_dict(self) -> dict:
        return {
            'taskId': self.task_id,
            'subtaskId': self.subtask_id,
            'verificationResult': self.verification_result,
            'paymentTs': self.payment_ts,
            'reason': self.reason
        }


class Event(object):
    """ Events: task, subtask, resource and subtask verification result"""

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

    def __init__(self,
                 node_id: str,
                 task_type: TaskType,
                 request_json: dict,
                 known_tasks: Dict[str, TaskHeader]
                 ):
        self.node_id = node_id
        self.task_type: TaskType = task_type
        self.update(request_json)
        self.stats: Counter = Counter()
        self.event_counter: int = 0
        # TODO: events TTL and cleanup
        self.events: Dict[str, Event] = dict()

        for task_id, header in known_tasks.items():
            if header.environment.lower() != self.task_type.name.lower():
                continue

            self.add_task_event(header)

        dispatcher.connect(self.add_task_event, signal='golem.task')
        dispatcher.connect(self._remove_task_event, signal='golem.task.removed')

    def update(self, request_json: dict):
        self.name = request_json.get('name', '')
        self.min_price = int(request_json['minPrice'])
        self.performance = float(request_json.get('performance', 0.0))
        self.max_cpu_cores = int(request_json['maxCpuCores'])
        self.max_memory_size = int(request_json['maxMemorySize'])
        self.max_disk_size = int(request_json['maxDiskSize'])
        self.eth_pub_key: Optional[str] = request_json.get('ethPubKey')

    def _add_event(self, event_hash: str, **kw):
        if event_hash in self.events:
            raise Exception('duplicated event hash %r: %r' % (event_hash, kw))

        event = Event(self.event_counter, **kw)
        self.event_counter += 1
        self.events[event_hash] = event

    def _remove_task_event(self, task_id: str):
        # TODO: remove also subtasks and resources?
        # this is bad idea since task can be removed
        # while subtask is still being computed
        pass
        # del self.events[task_id]

    def add_task_event(self, header: TaskHeader):
        self._add_event(header.task_id, task=Task(header))

    def want_subtask(self, task_server: TaskServer, task_id: str) -> bool:
        if task_id not in self.events:
            return False

        self.set_config_to(task_server.config_desc)
        task_server.request_task(task_id, self.performance, self.eth_pub_key)
        dispatcher.connect(self.add_subtask_event,
                           signal='golem.subtask')
        self.increment(SubtaskStatus.requested)
        return True

    def add_subtask_event(self, event='default', **kwargs) -> None:
        # TODO: persist or read existing subtasks upon start
        logger.debug('event: %r, kwargs: %r', event, kwargs)
        subtask = Subtask(**kwargs)
        if event == 'started' and subtask.task_id in self.events:
            self._add_event(subtask.subtask_id, subtask=subtask)
            dispatcher.disconnect(self.add_subtask_event,
                                  signal='golem.subtask')
            dispatcher.connect(self.add_resource_event,
                               signal='golem.resource')
        else:
            logger.warning('unexpected subtask event for %s/%s: %r' % (
                self.node_id, self.task_type, kwargs
            ))

    # TODO: remove from events or mark cancelled
    def cancel_subtask(self, task_server: TaskServer, subtask_id: str) -> bool:
        if subtask_id not in self.events \
                or subtask_id not in task_server.task_sessions:
            return False

        self.set_config_to(task_server.config_desc)
        task_server.task_sessions[subtask_id].send_subtask_cancel(subtask_id)
        dispatcher.disconnect(self.add_resource_event,
                              signal='golem.resource')
        self.increment(SubtaskStatus.cancelled)
        return True

    def add_resource_event(self, **kwargs) -> None:
        logger.debug('kwargs: %r ', kwargs)
        resource = Resource(**kwargs)
        if resource.subtask_id in self.events:
            self._add_event(f'rs-{resource.subtask_id}', resource=resource)
            dispatcher.disconnect(self.add_resource_event,
                                  signal='golem.resource')
        else:
            logger.warning('unexpected resource event for %s/%s: %r' % (
                self.node_id, self.task_type, kwargs
            ))

    def finish_subtask(self, task_server: TaskServer, root_path: str,
                       subtask_id: str, request_json: dict) -> bool:
        if subtask_id not in self.events \
                or subtask_id not in task_server.task_sessions\
                or request_json is None:
            return False

        subtask = self.events[subtask_id].subtask
        status = SubtaskStatus.match(request_json['status'])
        self.set_config_to(task_server.config_desc)

        # TODO: SubtaskStatus.timedout is not send(?), but should be counted
        if status == SubtaskStatus.succeeded:
            result_path = Path(root_path).joinpath(request_json['path'])
            result = {"data": [str(p) for p in result_path.glob('*')]}

            # TODO: should we call
            # golem_client.task_server.task_computer.__task_finished(subtask)
            task_server.send_results(subtask_id, subtask.task_id, result)

        elif status == SubtaskStatus.failed:
            reason = request_json['reason']
            task_server.send_task_failed(subtask_id, subtask.task_id, reason)

        else:
            logger.warning('wrong %s result for subtask %s', status, subtask_id)
            raise InvalidSubtaskStatus(f'subtask result status {status} '
                                       'must be one of: succeeded or failed')

        dispatcher.connect(self.add_result_verification_event,
                           signal='golem.message')
        self.increment(status)
        return True

    def add_result_verification_event(self, **kwargs) -> None:
        logger.debug('kwargs: %r ', kwargs)
        msg = kwargs['message']
        if msg.subtask_id in self.events \
                and (isinstance(msg, SubtaskResultsAccepted)
                     or isinstance(msg, SubtaskResultsRejected)):
            self._add_event(f'rv-{msg.subtask_id}', subtask_verification=(
                SubtaskVerification(msg)))
            dispatcher.disconnect(self.add_result_verification_event,
                                  signal='golem.message')

    def increment(self, status: Union[SubtaskStatus, str]) -> None:
        if isinstance(status, str):
            status = SubtaskStatus.match(status)
        self.stats.update([status.name])

    def events_after(self, event_id: int) -> List[Event]:
        if event_id >= self.event_counter:
            raise RuntimeError(f'event id {event_id} should be less than '
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
            'nodeId': self.node_id,
            'taskType': self.task_type.name,
            'subscription': {
                'name': self.name,
                'minPrice': self.min_price,
                'performance': self.performance,
                'maxCpuCores': self.max_cpu_cores,
                'maxMemorySize': self.max_memory_size,
                'maxDiskSize': self.max_disk_size,
                'ethPubKey': self.eth_pub_key,
            },
            'subtaskStats': dict(self.stats)
        }

    def __str__(self):
        return f'Subscription {self.name}({self.node_id}, {self.task_type})'
