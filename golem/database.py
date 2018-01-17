import abc
import datetime
import logging
from functools import partial
from queue import Queue, Empty
from threading import Thread, Event

from peewee import RawQuery, UpdateQuery, InsertQuery, DeleteQuery, Model
from twisted.internet.defer import Deferred

log = logging.getLogger('golem.db')


class DeferredEvent(Event):

    def __init__(self):
        super().__init__()
        self._deferred = Deferred()

    def wait(self, timeout=None):
        super().wait(timeout)
        return self

    @property
    def result(self):
        return self._deferred.result

    def callback(self, *args, **kwargs):
        self._deferred.callback(*args, **kwargs)
        self.set()

    def errback(self, *args, **kwargs):
        self._deferred.errback(*args, **kwargs)
        self.set()

    def addCallback(self, *args, **kwargs):
        self._deferred.addCallback(*args, **kwargs)
        return self

    def addErrback(self, *args, **kwargs):
        self._deferred.addErrback(*args, **kwargs)
        return self

    def addCallbacks(self, *args, **kwargs):
        self._deferred.addCallbacks(*args, **kwargs)
        return self

    def addBoth(self, *args, **kwargs):
        self._deferred.addBoth(*args, **kwargs)
        return self

    def chainDeferred(self, deferred):
        self._deferred.chainDeferred(deferred)
        return self


class DelegateQuery(abc.ABC):

    def __init__(self) -> None:
        self.evt = DeferredEvent()

    def execute(self) -> DeferredEvent:
        DatabaseService.submit(self)
        return self.evt

    @abc.abstractmethod
    def do_execute(self):
        pass


class RawDelegateQuery(DelegateQuery, RawQuery):

    def __init__(self, model, query, *params):
        DelegateQuery.__init__(self)
        RawQuery.__init__(self, model, query, *params)

    def do_execute(self):
        return RawQuery.execute(self)


class UpdateDelegateQuery(DelegateQuery, UpdateQuery):

    def __init__(self, model_class, update=None):
        DelegateQuery.__init__(self)
        UpdateQuery.__init__(self, model_class, update)

    def do_execute(self):
        return UpdateQuery.execute(self)


class InsertDelegateQuery(DelegateQuery, InsertQuery):

    def __init__(self, model_class, field_dict=None, rows=None, fields=None,
                 query=None, validate_fields=False):

        DelegateQuery.__init__(self)
        InsertQuery.__init__(self, model_class, field_dict, rows,
                             fields, query, validate_fields)

    def do_execute(self):
        return InsertQuery.execute(self)


class DeleteDelegateQuery(DelegateQuery, DeleteQuery):

    def __init__(self, model_class):
        DelegateQuery.__init__(self)
        DeleteQuery.__init__(self, model_class)

    def do_execute(self):
        return DeleteQuery.execute(self)


class SaveDelegatePseudoQuery(DelegateQuery):

    def __init__(self, instance, force_insert, only=None,
                 prepare_instance=False):

        super(SaveDelegatePseudoQuery, self).__init__()

        self.instance = instance
        self.force_insert = force_insert
        self.only = only
        self.prepare_instance = prepare_instance

    def do_execute(self):
        result = self.instance.save(force_insert=self.force_insert,
                                    only=self.only,
                                    __do_save__=True)
        if self.prepare_instance:
            self.instance._prepare_instance()
        return result

    @property
    def database(self):
        return self.instance._meta.database

    @database.setter
    def database(self, db):
        self.instance._meta.database = db

    def clone(self):
        return self


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
        return InsertDelegateQuery(cls,
                                   rows=rows,
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
    def create(cls, **query) -> DeferredEvent:
        return SaveDelegatePseudoQuery(cls(**query),
                                       force_insert=True,
                                       prepare_instance=True).execute()

    @classmethod
    def get_or_create(cls, __wait__=False, **kwargs):
        result, created = super().get_or_create(**kwargs)
        # if __wait__:
        #     result.wait()
        return result, created

    def save(self,
             force_insert=False,
             only=None,
             __do_save__=None) -> DeferredEvent:

        if __do_save__:
            return super().save(force_insert, only)
        return SaveDelegatePseudoQuery(self, force_insert, only).execute()


class DatabaseService:

    QUEUE_TIMEOUT = datetime.timedelta(seconds=1).total_seconds()
    queue = Queue()

    def __init__(self, db):
        self._db = db
        self._db_conn = None
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

        if self._thread.is_alive():
            self._thread.join()

    @classmethod
    def submit(cls, query: DelegateQuery) -> None:
        """
        Insert a query into the queue
        :param query: Query to execute
        """
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
        self._db.connect()

        while not self._stop_event.is_set():
            self._loop()

        if not self._db.is_closed():
            self._db.close()

    def _loop(self) -> None:

        try:
            query = self.queue.get(True, self._queue_timeout)
        except Empty:
            return

        try:
            #query = query.clone()
            query.database = self._db
            with self._db.transaction(transaction_type='immediate'):
                result = query.do_execute()
        except Exception as exc:
            handler = partial(self._log_error, query)
            query.evt.addErrback(handler)
            query.evt.errback(exc)
        else:
            query.evt.callback(result)

    @staticmethod
    def _log_error(query, error):
        log.error("Cannot execute %r: %r", query, error)
        return error

