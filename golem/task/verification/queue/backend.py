from abc import ABC, abstractmethod
from typing import Callable, Optional, Tuple

from peewee import IntegrityError

from golem.model import QueuedVerification, db
from golem.task import SubtaskId, TaskId

PriorityFn = Callable[[], int]


class QueueBackend(ABC):

    @abstractmethod
    def put(
            self,
            task_id: TaskId,
            subtask_id: SubtaskId,
            priority: Optional[int],
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get(
            self,
    ) -> Optional[Tuple[TaskId, SubtaskId]]:
        raise NotImplementedError

    @abstractmethod
    def update_not_prioritized(
            self,
            priority_fn: PriorityFn,
    ) -> None:
        raise NotImplementedError


class DatabaseQueueBackend(QueueBackend):

    QueuedItem = QueuedVerification

    def put(
            self,
            task_id: TaskId,
            subtask_id: SubtaskId,
            priority: Optional[int],
    ) -> bool:
        try:
            QueuedVerification.create(
                task_id=task_id,
                subtask_id=subtask_id,
                priority=priority)
        except IntegrityError:
            return False
        return True

    def get(
            self,
    ) -> Optional[Tuple[TaskId, SubtaskId]]:
        with db.transaction():
            try:
                queued = QueuedVerification.select() \
                    .where(QueuedVerification.priority.is_null(False)) \
                    .order_by(+QueuedVerification.priority) \
                    .limit(1) \
                    .execute()
                queued = list(queued)[0]
            except IndexError:
                return None
            queued.delete_instance()

        return queued.task_id, queued.subtask_id

    def update_not_prioritized(
            self,
            priority_fn: PriorityFn,
    ) -> None:
        with db.transaction():
            results = QueuedVerification.select() \
                .where(QueuedVerification.priority.is_null(True)) \
                .order_by(+QueuedVerification.created_date) \
                .execute()

            for result in results:
                result.priority = priority_fn()
                result.save()