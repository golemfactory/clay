import datetime
import logging
import threading
import typing

import golem_messages
from golem_messages import exceptions as msg_exceptions

from golem import decorators
from golem import model
from golem.core import variables


if typing.TYPE_CHECKING:
    # pylint: disable=ungrouped-imports,unused-import
    from golem_messages import message


logger = logging.getLogger(__name__)
READ_LOCK = threading.Lock()


def put(node_id: str, msg: 'message.base.Base') -> None:
    db_model = model.QueuedMessage.from_message(node_id, msg)
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
        yield msg


def waiting() -> typing.Iterator[str]:
    for db_row in model.QueuedMessage.select(
            model.QueuedMessage.node,
    ).group_by(model.QueuedMessage.node):
        yield db_row.node


@decorators.run_with_db()
def sweep() -> None:
    """Sweep ancient messages"""
    with READ_LOCK:
        oldest_allowed = datetime.datetime.now() \
            - variables.MESSAGE_QUEUE_MAX_AGE
        count = model.QueuedMessage.delete().where(
            model.QueuedMessage.created_date < oldest_allowed,
        ).execute()
    if count:
        logger.info('Sweeped ancient messages from queue. count=%d', count)
