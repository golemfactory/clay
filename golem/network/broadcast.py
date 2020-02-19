import logging
import typing

import peewee

from golem import decorators
from golem import model
from golem.core import variables
from golem.core.databuffer import DataBuffer


logger = logging.getLogger(__name__)


class BroadcastError(Exception):
    pass


class BroadcastList(list):
    @classmethod
    def from_bytes(cls, b: bytes) -> typing.List[model.Broadcast]:
        db = DataBuffer()
        db.append_bytes(b)
        result = []
        for cnt, broadcast_binary in enumerate(db.get_len_prefixed_bytes()):
            if cnt >= 10:
                break
            try:
                b = model.Broadcast.from_bytes(broadcast_binary)
                b.verify_signature(public_key=variables.BROADCAST_PUBKEY)
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

    def to_bytes(self) -> bytes:
        db = DataBuffer()
        for broadcast in self:
            assert isinstance(broadcast, model.Broadcast)
            db.append_len_prefixed_bytes(broadcast.to_bytes())
        return db.read_all()


def prepare_handshake() -> BroadcastList:
    query = model.Broadcast.select().where(
        model.Broadcast.broadcast_type == model.Broadcast.TYPE.Version,
    )
    bl = BroadcastList()
    if query.exists():
        bl.append(query.order_by('-timestamp')[0])
    logger.debug('Prepared handshake: %s', bl)
    return bl


@decorators.run_with_db()
def sweep() -> None:
    logger.info('Sweeping broadcasts')
    max_timestamp = model.Broadcast.select(
        peewee.fn.MAX(model.Broadcast.timestamp),
    ).scalar()
    count = model.Broadcast.delete().where(
        model.Broadcast.broadcast_type == model.Broadcast.TYPE.Version,
        model.Broadcast.timestamp < max_timestamp,
    ).execute()
    if count:
        logger.info('Sweeped broadcasts. count=%d', count)
