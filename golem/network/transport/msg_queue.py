import datetime
import logging
import sqlite3
import threading
import typing

import golem_messages
from golem_messages import exceptions as msg_exceptions
from golem_messages import message
import peewee

from golem import decorators
from golem import model
from golem.core.common import default_now, short_node_id


logger = logging.getLogger(__name__)
READ_LOCK = threading.Lock()
# CLasses that aren't allowed in queue
FORBIDDEN_CLASSES = (
    message.base.Disconnect,
    message.base.Hello,
    message.base.RandVal,
)


def put(
        node_id: str,
        msg: message.base.Message,
        timeout: typing.Optional[datetime.timedelta] = None
) -> None:
    assert not isinstance(msg, FORBIDDEN_CLASSES),\
        "Disconnect message shouldn't be in a queue"
    logger.debug("saving into queue node_id=%s, msg=%r",
                 short_node_id(node_id), msg)
    deadline_utc = (default_now() + timeout) if timeout else None
    db_model = model.QueuedMessage.from_message(node_id, msg, deadline_utc)
    db_model.save()


def get(node_id: str) -> typing.Iterator['message.base.Base']:
    while True:
        with READ_LOCK:
            try:
                db_model = model.QueuedMessage.select()\
                    .where(
                        model.QueuedMessage.node == node_id,
                    ).order_by(model.QueuedMessage.created_date).get()
            except model.QueuedMessage.DoesNotExist:
                return

            try:
                if db_model.deadline <= default_now():
                    logger.debug(
                        'deleting message past its deadline.'
                        ' db_model=%s, deadline=%s',
                        db_model,
                        db_model.deadline
                    )
                    continue

                msg = db_model.as_message()
            except msg_exceptions.VersionMismatchError:
                logger.info(
                    'Dropping message with mismatched GM version.'
                    ' db_model=%s, gm_version=%s, msg=%s',
                    db_model,
                    golem_messages.__version__,
                    db_model.msg_data,
                )
                continue
            except msg_exceptions.MessageError:
                logger.info(
                    'Invalid message in queue.'
                    ' db_model=%s',
                    db_model,
                    exc_info=True,
                )
                continue
            finally:
                db_model.delete_instance()
        logger.debug("got from queue node_id=%s, msg=%r",
                     short_node_id(node_id), msg)
        yield msg


def waiting() -> typing.Iterator[str]:
    query = model.QueuedMessage.select(
        model.QueuedMessage.node,
    ).where(
        model.QueuedMessage.deadline > default_now()
    ).group_by(model.QueuedMessage.node)
    try:
        for db_row in query:
            yield db_row.node
    except (
            sqlite3.ProgrammingError,
            peewee.OperationalError,
    ):
        # SEE also: golem.database.database
        #           .GolemSqliteDatabase.execute_sql
        # Here we're using peewee.QueryResultWrapper.iterate()
        # and have to duplicate error handling.
        logger.debug("DB Error", exc_info=True)


@decorators.run_with_db()
def sweep() -> None:
    """Sweep messages"""
    with READ_LOCK:
        count = model.QueuedMessage.delete().where(
            model.QueuedMessage.deadline <= default_now()
        ).execute()

    if count:
        logger.info('Sweeped messages from queue. count=%d', count)
