import abc
import datetime
import logging
from queue import Queue, Empty
from threading import Thread, Event

from peewee import RawQuery, UpdateQuery, InsertQuery, DeleteQuery, DataError, \
    ProgrammingError, NotSupportedError, \
    IntegrityError, PeeweeException, Model

log = logging.getLogger('golem.db')


class DelegateQuery(abc.ABC):

    def execute(self):
        DatabaseService.submit(self)


class RawDelegateQuery(RawQuery, DelegateQuery):

    def do_execute(self):
        return RawQuery.execute(self)


class UpdateDelegateQuery(UpdateQuery, DelegateQuery):

    def do_execute(self):
        return UpdateQuery.execute(self)


class InsertDelegateQuery(InsertQuery, DelegateQuery):

    def do_execute(self):
        return InsertQuery.execute(self)


class DeleteDelegateQuery(DeleteQuery, DelegateQuery):

    def do_execute(self):
        return DeleteQuery.execute(self)


class SaveDelegatePseudoQuery(DelegateQuery):

    def __init__(self, instance):
        self.instance = instance
        self.ready = Event()

    def do_execute(self):
        try:
            self.instance.save(force_insert=True, do_save=True)
            self.instance._prepare_instance()
        finally:
            self.ready.set()


class DelegateModel(Model):

    @classmethod
    def update(cls, __data=None, **update):
        fdict = __data or {}
        fdict.update([(cls._meta.fields[f], update[f]) for f in update])
        return UpdateDelegateQuery(cls, fdict)

    # We cannot override "insert", as it is called in "save"
    @classmethod
    def insert_one(cls, __data=None, **insert):
        fdict = __data or {}
        fdict.update([(cls._meta.fields[f], insert[f]) for f in insert])
        return InsertDelegateQuery(cls, fdict)

    @classmethod
    def insert_many(cls, rows, validate_fields=True):
        return InsertDelegateQuery(cls, rows=rows,
                                   validate_fields=validate_fields)

    @classmethod
    def insert_from(cls, fields, query):
        return InsertDelegateQuery(cls, fields=fields, query=query)

    @classmethod
    def delete(cls):
        return DeleteDelegateQuery(cls)

    @classmethod
    def raw(cls, sql, *params):
        return RawDelegateQuery(cls, sql, *params)

    @classmethod
    def create(cls, **query) -> Event:
        instance = cls(**query)

        query = SaveDelegatePseudoQuery(instance)
        query.execute()
        return query.ready

    @classmethod
    def get_or_create(cls, _wait=False, **kwargs):
        result, created = super().get_or_create(**kwargs)
        if created and _wait:
            result.wait()
        return result, created

    def save(self, force_insert=False, only=None, do_save=False) -> Event:
        if do_save:
            return super().save(force_insert, only)

        query = SaveDelegatePseudoQuery(self)
        query.execute()
        return query.ready


class DatabaseService:

    QUEUE_TIMEOUT = datetime.timedelta(seconds=2).total_seconds()
    queue = Queue()

    def __init__(self, db):
        self._db = db
        self._thread = None
        self._queue_timeout = None
        self._stop_event = Event()

    def start(self) -> None:
        """
        Starts the service if not already running.
        """
        if self.running:
            return log.warning('Database service is already running')

        self._stop_event.clear()
        self._queue_timeout = self.QUEUE_TIMEOUT
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """
        Stops the service and saves remaining messages.
        """
        self._stop_event.set()
        self._queue_timeout = 0
        while not self.queue.empty():
            self._loop()

    @classmethod
    def submit(cls, query: DelegateQuery):
        cls.queue.put(query)

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

    def _run(self) -> None:
        """
        Thread activity method.
        """
        while not self._stop_event.is_set():
            self._loop()

    def _loop(self) -> None:
        try:
            query = self.queue.get(True, self._queue_timeout)
        except Empty:
            return

        try:

            query.database = self._db
            query.do_execute()

        except (DataError, ProgrammingError, NotSupportedError,
                TypeError, IntegrityError) as exc:

            log.error("Cannot execute query %r: %r",
                      query, exc)
        except PeeweeException as exc:

            log.warning("Temporary error while executing query %r: %r",
                        query, exc)
            self.queue.put(query)


