import logging
import typing

import peewee

from golem import decorators
from golem import model
from golem.config import active
from golem.core.databuffer import DataBuffer


logger = logging.getLogger(__name__)


class BroadcastError(Exception):
    pass


def list_from_bytes(b: bytes) -> typing.List[model.Broadcast]:
    db = DataBuffer()
    db.append_bytes(b)
    result = []
    for cnt, broadcast_binary in enumerate(db.get_len_prefixed_bytes()):
        if cnt >= 10:
            break
        try:
            b = model.Broadcast.from_bytes(broadcast_binary)
            b.verify_signature(public_key=active.BROADCAST_PUBKEY)
            result.append(b)
        except BroadcastError as e:
            logger.debug(
                'Invalid broadcast received: %s. b=%r',
                e,
                broadcast_binary,
            )
        except Exception:  # pylint: disable=broad-except
            logger.debug(
                'Invalid broadcast received: %r',
                broadcast_binary,
                exc_info=True,
            )
    return result


def list_to_bytes(l: typing.List[model.Broadcast]) -> bytes:
    db = DataBuffer()
    for broadcast in l:
        assert isinstance(broadcast, model.Broadcast)
        db.append_len_prefixed_bytes(broadcast.to_bytes())
    return db.read_all()


def prepare_handshake() -> typing.List[model.Broadcast]:
    query = model.Broadcast.select().where(
        model.Broadcast.broadcast_type == model.Broadcast.TYPE.Version,
    )
    bl = []
    if query.exists():
        bl.append(query.order_by('-timestamp')[0])
    logger.debug('Prepared handshake: %s', bl)
    return bl


@decorators.run_with_db()
def sweep() -> None:
    max_timestamp = model.Broadcast.select(
        peewee.fn.MAX(model.Broadcast.timestamp),
    ).scalar()
    count = model.Broadcast.delete().where(
        model.Broadcast.broadcast_type == model.Broadcast.TYPE.Version,
        model.Broadcast.timestamp < max_timestamp,
    ).execute()
    if count:
        logger.info('Sweeped broadcasts. count=%d', count)
