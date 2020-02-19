import codecs

from golem import model
from golem.core import common
from golem.core import variables
from golem.rpc import utils as rpc_utils


@rpc_utils.expose('broadcast.hash')
def hash_(
        timestamp: int,
        broadcast_type: int,
        data_hex: str,
) -> str:
    """Generate hash of a broadcast that should be signed by client
       before pushing
    """
    type_ = model.Broadcast.TYPE(int(broadcast_type))
    data = codecs.decode(data_hex, 'hex')  # type: ignore
    bc = model.Broadcast(
        broadcast_type=type_,
        timestamp=int(timestamp),
        data=data,
    )
    return codecs.encode(bc.get_hash(), 'hex').decode()  # type: ignore


@rpc_utils.expose('broadcast.push')
def push(
        timestamp: int,
        broadcast_type: int,
        data_hex: str,
        signature_hex: str,
):
    """Push signed broadcast into the p2p network
    """
    data = codecs.decode(data_hex, 'hex')  # type: ignore
    signature = codecs.decode(signature_hex, 'hex')  # type: ignore
    bc = model.Broadcast(
        broadcast_type=model.Broadcast.TYPE(int(broadcast_type)),
        timestamp=int(timestamp),
        data=data,
        signature=signature,
    )
    bc.verify_signature(public_key=variables.BROADCAST_PUBKEY)
    if not bc.process():
        raise RuntimeError("Broadcast rejected")


@rpc_utils.expose('broadcast.list')
def list_():
    """Return all known broadcasts from local DB
    """
    return [
        {
            'timestamp': bc.timestamp,
            'broadcast_type': bc.broadcast_type.value,
            'broadcast_type_name': bc.broadcast_type.name,
            'data_hex': codecs.encode(bc.data, 'hex').decode(),
            'created_date': common.datetime_to_timestamp_utc(bc.created_date),
        }
        for bc
        in model.Broadcast.select().order_by('created_date')
    ]
