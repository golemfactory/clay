import datetime
import logging
import operator
import queue
import threading
from abc import abstractmethod, ABC
from functools import reduce, wraps
from typing import List

from golem_messages import message
from peewee import (PeeweeException, DataError, ProgrammingError,
                    NotSupportedError, Field)

from golem.core.service import IService
from golem.model import NetworkMessage, Actor

logger = logging.getLogger('golem.network.history')


class MessageNotFound(Exception):
    pass


class MessageHistoryService(IService):
    """
    The purpose of this class is to:
    - save NetworkMessages (in background)
    - remove given NetworkMessages (in background)
    - sweep NetworkMessages past their MESSAGE_LIFETIME every ~ SWEEP_INTERVAL
      (in background)
    - retrieve, save and remove NetworkMessages in-place via *_sync methods

    Assumptions:
    - NetworkMessages have to be saved ASAP
    - removal and sweeping is not critical and can be slightly delayed

    Background operations performed by this service do not fit the looping call
    model of golem.core.service.LoopingCallService.
    """

    MESSAGE_LIFETIME = datetime.timedelta(days=1)
    SWEEP_INTERVAL = datetime.timedelta(hours=12)
    QUEUE_TIMEOUT = datetime.timedelta(seconds=2).total_seconds()

    # Decorators (at the end of this file) need to access an instance
    # of MessageHistoryService
    instance = None

    def __init__(self):
        IService.__init__(self)

        if self.__class__.instance is None:
            self.__class__.instance = self

        self._thread = None  # set in start
        self._queue_timeout = None  # set in start
        self._stop_event = threading.Event()
        self._save_queue = queue.Queue()
        self._remove_queue = queue.Queue()
        self._sweep_ts = datetime.datetime.now()

    def run(self) -> None:
        """
        Thread activity method.
        """
        while not self._stop_event.is_set():
            self._loop()

    @property
    def running(self) -> bool:
        """
        Returns whether the service was stopped by the user.
        """
        return (
            self._thread and
            self._thread.is_alive() and
            not self._stop_event.is_set()
        )

    def start(self) -> None:
        if self.running:
            return

        self._stop_event.clear()
        self._queue_timeout = self.QUEUE_TIMEOUT
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """
        Stops the service and saves remaining messages.
        """
        self._stop_event.set()
        self.instance = None

        self._queue_timeout = 0
        while not self._save_queue.empty():
            self._loop()

    @classmethod
    def get_sync(cls, task: str, **properties) -> List[NetworkMessage]:
        """
        Returns Task-related messages
        :param task: Task id
        :param properties: Optional NetworkMessage properties
        :return: Collection of NetworkMessage
        """
        clauses = cls.build_clauses(task=task, **properties)

        result = NetworkMessage.select() \
            .where(reduce(operator.and_, clauses)) \
            .order_by(+NetworkMessage.msg_date)

        return list(result)

    @classmethod
    def get_sync_as_message(cls, *args, **kwargs) -> message.Message:
        db_result = cls.get_sync(*args, **kwargs)
        if not db_result:
            raise MessageNotFound()
        db_msg = db_result[0]
        return db_msg.as_message()

    def add(self, msg_dict: dict) -> None:
        """
        Appends the dict message representation to the save queue.
        :param msg_dict:
        """
        if msg_dict:
            self._save_queue.put(msg_dict)

    def add_sync(self, msg_dict: dict) -> None:
        """
        Saves a message in the database.
        :param msg_dict: Message to save
        """
        try:
            msg = NetworkMessage(**msg_dict)
            msg.save()
        except (DataError, ProgrammingError, NotSupportedError) as exc:
            # Unrecoverable error
            logger.error("Cannot save message '%s' to database: %r",
                         msg.msg_cls, exc)
        except PeeweeException:
            # Temporary error
            logger.debug("Message '%s' save queued", msg.msg_cls)
            self._save_queue.put(msg_dict)

    def remove(self, task: str, **properties) -> None:
        """
        Appends task id to the removal queue. Has lower priority than adding
        a new message.
        :param task: Task id
        """
        if task:
            self._remove_queue.put((task, properties))

    def remove_sync(self, task: str, **properties) -> None:
        """
        Removes messages
        :param task: Task id
        :param properties: Optional NetworkMessage properties
        :return: None
        """
        clauses = self.build_clauses(task=task, **properties)

        try:
            NetworkMessage.delete() \
                .where(reduce(operator.and_, clauses)) \
                .execute()
        except (DataError, ProgrammingError, NotSupportedError) as exc:
            # Unrecoverable error
            logger.error("Cannot remove task messages from the database: "
                         "(task: '%s', parameters: %r): %r",
                         task, properties, exc)
        except PeeweeException:
            # Temporary error
            logger.debug("Task %s (%r) message removal queued",
                         task, properties)
            self._remove_queue.put((task, properties))

    @staticmethod
    def build_clauses(**properties) -> List[bool]:
        """
        :param properties: NetworkMessage properties to filter (equality)
        :return: List of peewee query clauses
        """
        clauses = []

        for name, value in properties.items():
            prop = getattr(NetworkMessage, name, None)

            if isinstance(prop, Field):
                clauses.append((prop == value))
            else:
                logger.error("Invalid property: %s", name)

        return clauses

    def _loop(self) -> None:
        """
        Main service loop.
        - calls _sweep every SWEEP_INTERVAL
        - saves queued (1) messages to database (FIFO)
        - removes queued (2) messages from database
        """

        # Sweep messages.
        # With big enough SWEEP_INTERVAL, _sweep time becomes negligible
        now = datetime.datetime.now()
        if now >= self._sweep_ts:
            self._sweep()
            self._sweep_ts = now + self.SWEEP_INTERVAL

        # Remove messages
        try:
            task, parameters = self._remove_queue.get(False)
        except queue.Empty:
            pass
        else:
            self.remove_sync(task, **parameters)

        # Save messages
        try:
            msg_dict = self._save_queue.get(True, self._queue_timeout)
        except queue.Empty:
            pass
        else:
            self.add_sync(msg_dict)

    def _sweep(self) -> None:
        """
        Removes messages older than MESSAGE_LIFETIME.
        """
        logger.info("Sweeping messages")
        oldest = datetime.datetime.now() - self.MESSAGE_LIFETIME

        try:
            NetworkMessage.delete() \
                .where(NetworkMessage.msg_date <= oldest) \
                .execute()
        except PeeweeException as exc:
            logger.error("Message sweep failed: %r", exc)


##############
# INTERFACES #
##############


class IMessageHistoryProvider(ABC):

    @abstractmethod
    def message_to_model(self, msg: 'golem_messages.message.Message',
                         local_role: Actor,
                         remote_role: Actor) -> dict:
        """
        Converts a message to its database model dictionary representation.

        MessageHistoryService operates in a separate thread, whereas peewee
        models are created on per-connection (here: per-thread) basis. If
        MessageHistoryService used objects created in another thread, it would
        lock the database for that thread.

        The returned dict representation is used for creating NetworkMessage
        models in MessageHistoryService thread.

        :param msg: Session message
        :param local_role: Local node's role in computation
        :param remote_role: Remote node's role in computation
        :return: Dict representation of NetworkMessage
        """

##############
# DECORATORS #
##############


def record_history(local_role, remote_role):
    def decorator(func):

        @wraps(func)
        def wrapper(self, msg, *args, **kwargs):
            service = MessageHistoryService.instance
            model = self.message_to_model(msg, local_role, remote_role)

            if model and service:
                service.add(model)
            else:
                logger.error("Cannot log message: %r", msg)
            return func(self, msg, *args, **kwargs)

        return wrapper
    return decorator


provider_history = record_history(local_role=Actor.Provider,
                                  remote_role=Actor.Requestor)

requestor_history = record_history(local_role=Actor.Requestor,
                                   remote_role=Actor.Provider)
