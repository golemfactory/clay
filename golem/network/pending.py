import datetime
from typing import List, Iterator, Optional, Tuple

import operator
from functools import reduce
from golem_messages import serializer
from peewee import CharField, IntegerField, TextField, BlobField

from golem.database import GolemSqliteDatabase, Database
from golem.model import JsonField, BaseModel, collect_db_models, \
    collect_db_fields
from golem.transactions.ethereum.ethereumpaymentskeeper import EthAccountInfo

ANY = object()
db = GolemSqliteDatabase(
    None,
    threadlocals=True,
    pragmas=(
        ('foreign_keys', True),
        ('busy_timeout', 1000),
        ('journal_mode', 'WAL')
    ))


# Fields

class ResultOwnerField(JsonField):

    def db_value(self, value):
        dictionary = value.__dict__ if value else None
        return super().db_value(dictionary)

    def python_value(self, value):
        dictionary = super().python_value(value)
        return EthAccountInfo(**dictionary)


class MessageSlotsField(BlobField):

    def db_value(self, value):
        try:
            return serializer.dumps(value)
        except Exception:  # pylint: disable=broad-except
            return None

    def python_value(self, value):
        try:
            return serializer.loads(value)
        except Exception:  # pylint: disable=broad-except
            return None


# Models

class PendingObjectModel(BaseModel):
    """ Base class for pending message and session models"""

    class Meta:
        database = db

    node_id = CharField(index=True)  # Receiving node
    task_id = CharField(null=True)
    subtask_id = CharField(null=True)

    @classmethod
    def select_clauses(cls,
                       node_id: Optional[object] = ANY,
                       task_id: Optional[object] = ANY,
                       subtask_id: Optional[object] = ANY) -> List[Tuple]:

        """ Builds and returns 'with' statement clauses """

        clauses = []

        if node_id is not ANY:
            clauses.append((cls.node_id == node_id))
        if task_id is not ANY:
            clauses.append((cls.task_id == task_id))
        if subtask_id is not ANY:
            clauses.append((cls.subtask_id == subtask_id))

        return reduce(operator.and_, clauses)


class PendingTaskSession(PendingObjectModel):

    node_id = CharField(index=True, unique=True)  # Force uniqueness
    result_owner = ResultOwnerField(null=True)
    err_msg = TextField(null=True)


class PendingMessage(PendingObjectModel):

    type = IntegerField()
    slots = MessageSlotsField()


# Mixins

class PendingMessagesMixin:

    @classmethod
    def put(cls,
            node_id: str,
            msg: 'Message',
            task_id: Optional[str] = None,
            subtask_id: Optional[str] = None) -> None:

        PendingMessage(
            node_id=node_id,
            type=msg.TYPE,
            slots=msg.slots(),
            task_id=task_id,
            subtask_id=subtask_id
        ).save(force_insert=True)

    @classmethod
    def get(cls,
            node_id: str,
            task_id: Optional[object] = ANY,
            subtask_id: Optional[object] = ANY) -> Iterator['PendingMessage']:

        """ Returns a message iterator.
            Can be used by an established TaskSession between ourselves and
            node_id to know what messages should be sent."""

        clauses = PendingMessage.select_clauses(node_id, task_id, subtask_id)
        return PendingMessage.select().where(clauses).iterator()

    @classmethod
    def exists(cls,
               node_id: str,
               task_id: Optional[object] = ANY,
               subtask_id: Optional[object] = ANY) -> bool:

        clauses = PendingMessage.select_clauses(node_id, task_id, subtask_id)
        return PendingMessage.select().where(clauses).exists()


class PendingTaskSessionsMixin:

    @classmethod
    def put_session(cls,
                    node_id: str,
                    task_id: Optional[str] = None,
                    subtask_id: Optional[str] = None,
                    result_owner: Optional[EthAccountInfo] = None,
                    err_msg: Optional[str] = None) -> None:

        PendingTaskSession(
            node_id=node_id,
            task_id=task_id,
            subtask_id=subtask_id,
            result_owner=result_owner,
            err_msg=err_msg
        ).save(force_insert=True)

    @classmethod
    def get_session(cls,
                    node_id: str,
                    task_id: Optional[object] = ANY,
                    subtask_id: Optional[object] = ANY
                    ) -> Iterator['PendingMessage']:

        clauses = PendingTaskSession.select_clauses(node_id, task_id,
                                                    subtask_id)
        return PendingTaskSession.select().where(clauses).iteartor()

    @classmethod
    def exists(cls,
               node_id: str,
               task_id: Optional[object] = ANY,
               subtask_id: Optional[object] = ANY) -> bool:

        clauses = PendingTaskSession.select_clauses(node_id, task_id,
                                                    subtask_id)
        return PendingTaskSession.select().where(clauses).exists()


# Manager

class PendingSessionMessages(PendingMessagesMixin,
                             PendingTaskSessionsMixin):

    class AuxDatabase(Database):
        SCHEMA_VERSION = 1

    LIFETIME = datetime.timedelta(days=3)

    def __init__(self,
                 db_dir: str,
                 db_name: str = 'session.db',
                 schemas_dir: Optional[str] = None):

        self._last_sweep_ts = None
        self._fields = DB_FIELDS
        self._models = DB_MODELS
        self._database = self.AuxDatabase(
            db,
            db_name=db_name,
            db_dir=db_dir,
            schemas_dir=schemas_dir,
            fields=self._fields,
            models=self._models
        )

    def sweep(self) -> None:
        now = datetime.datetime.now()

        for model in self._models:
            model.delete() \
                .where(model.created_date + self.LIFETIME <= now) \
                .execute()


DB_FIELDS = [cls for _, cls in collect_db_fields(__name__)]
DB_MODELS = [cls for _, cls in collect_db_models(__name__)]
