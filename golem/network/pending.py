import datetime
import json
import logging

import operator
from functools import reduce
from typing import Iterator, List, Optional, Tuple

from peewee import BlobField, CharField, IntegerField, TextField, DoesNotExist

from golem_messages import message, serializer  # noqa # pylint: disable=unused-import,import-error

from golem.core.simpleserializer import DictSerializer
from golem.database import Database, GolemSqliteDatabase
from golem.model import BaseModel, JsonField, collect_db_fields, \
    collect_db_models

logger = logging.getLogger(__name__)

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

class ResultOwnerField(TextField):

    def db_value(self, value):
        return json.dumps(DictSerializer.dump(value))

    def python_value(self, value):
        return DictSerializer.load(json.loads(value))


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

    class Meta:  # pylint: disable=too-few-public-methods
        database = db

    key_id = CharField(index=True)  # Receiving node
    task_id = CharField(null=True)
    subtask_id = CharField(null=True)

    @classmethod
    def build_select_clauses(cls,
                             key_id: Optional[object] = ANY,
                             task_id: Optional[object] = ANY,
                             subtask_id: Optional[object] = ANY) -> List[Tuple]:

        """ Builds and returns 'where' statement clauses """

        clauses = []

        if key_id is not ANY:
            clauses.append((cls.key_id == key_id))
        if task_id is not ANY:
            clauses.append((cls.task_id == task_id))
        if subtask_id is not ANY:
            clauses.append((cls.subtask_id == subtask_id))

        return reduce(operator.and_, clauses)


class PendingTaskSession(PendingObjectModel):

    address = CharField(null=True)
    port = IntegerField(null=True)
    node_info = JsonField(null=True)
    result_owner = ResultOwnerField(null=True)
    err_msg = TextField(null=True)

    @classmethod
    def from_session(cls, session) -> 'PendingTaskSession':
        return cls(
            key_id=session.key_id,
            task_id=session.task_id,
            subtask_id=session.subtask_id,
            node_info=session.node_info,
            result_owner=session.result_owner,
            err_msg=session.err_msg
        )

    def update_session(self, session) -> None:
        session.task_id = self.task_id
        session.subtask_id = self.subtask_id
        session.node_info = self.node_info
        session.result_owner = self.result_owner
        session.err_msg = self.err_msg


class PendingMessage(PendingObjectModel):

    type = IntegerField()
    slots = MessageSlotsField()

    def as_message(self):
        cls = message.registered_message_types[self.type]
        return cls(slots=self.slots)


# Mixins

class PendingMessagesMixin:

    @classmethod
    def put(cls,
            key_id: str,
            msg: message.base.Message,
            task_id: Optional[str] = None,
            subtask_id: Optional[str] = None) -> None:

        PendingMessage(
            key_id=key_id,
            type=msg.TYPE,
            slots=msg.slots(),
            task_id=task_id,
            subtask_id=subtask_id
        ).save(force_insert=True)

    @classmethod
    def get(cls,
            key_id: str,
            task_id: Optional[object] = ANY,
            subtask_id: Optional[object] = ANY
            ) -> Iterator[message.base.Message]:

        """ Returns a message iterator.
            Can be used by an established TaskSession between ourselves and
            key_id to know what messages should be sent."""

        clauses = PendingMessage.build_select_clauses(key_id, task_id,
                                                      subtask_id)
        iterator = PendingMessage.select() \
            .where(clauses) \
            .order_by(PendingMessage.created_date.asc()) \
            .iterator()

        for pending_msg in iterator:
            try:
                yield pending_msg.as_message()
            except Exception as exc:  # pylint: disable=broad-except
                logger.error('Cannot deserialize the pending message: %r', exc)
                logger.debug('Pending message (type %r) slots: %r',
                             pending_msg.type, pending_msg.slots)
            finally:
                pending_msg.delete_instance()

    @classmethod
    def exists(cls,
               key_id: str,
               task_id: Optional[object] = ANY,
               subtask_id: Optional[object] = ANY) -> bool:

        clauses = PendingMessage.build_select_clauses(key_id, task_id,
                                                      subtask_id)
        return PendingMessage.select().where(clauses).exists()


class PendingTaskSessionsMixin:

    @classmethod
    def put_session(cls, session) -> None:
        try:
            session = cls.get_session(session.key_id)
            session.delete_instance()
        except DoesNotExist:
            pass

        PendingTaskSession.from_session(session).save(force_insert=True)

    @classmethod
    def get_session(cls,
                    key_id: str,
                    task_id: Optional[object] = ANY,
                    subtask_id: Optional[object] = ANY) -> PendingTaskSession:

        clauses = PendingTaskSession.build_select_clauses(key_id, task_id,
                                                          subtask_id)
        return PendingTaskSession.get(clauses)

    @classmethod
    def get_sessions(cls) -> Iterator[PendingTaskSession]:

        return PendingTaskSession.select() \
            .order_by(+PendingTaskSession.created_date) \
            .iterator()


# Manager

class PendingSessionMessages(PendingMessagesMixin,
                             PendingTaskSessionsMixin):

    class AuxDatabase(Database):
        SCHEMA_VERSION = 1

    LIFETIME = datetime.timedelta(days=3)

    def __init__(self,
                 db_dir: str,
                 db_name: str = 'session.db',
                 schemas_dir: Optional[str] = None) -> None:

        self._last_sweep_ts = None
        self._fields = DB_FIELDS
        self._models = DB_MODELS
        self._database = self.AuxDatabase(
            db,
            db_name=db_name,
            db_dir=db_dir,
            schemas_dir=schemas_dir,
            fields=DB_FIELDS,
            models=DB_MODELS
        )

    def sweep(self) -> None:
        now = datetime.datetime.now()

        for model in self._models:
            model.delete() \
                .where(model.created_date + self.LIFETIME <= now) \
                .execute()

    def quit(self):
        self._database.close()


DB_FIELDS = [cls for _, cls in collect_db_fields(__name__)]
DB_MODELS = [cls for _, cls in collect_db_models(
    __name__, excluded=[BaseModel, PendingObjectModel]
)]
