from golem import model
from golem.config import active
from golem.core import common
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
    data = bytes.fromhex(data_hex)
    bc = model.Broadcast(
        broadcast_type=type_,
        timestamp=int(timestamp),
        data=data,
    )
    return bc.get_hash().hex()


@rpc_utils.expose('broadcast.push')
def push(
        timestamp: int,
        broadcast_type: int,
        data_hex: str,
        signature_hex: str,
):
    """Push signed broadcast into the p2p network
    """
    data = bytes.fromhex(data_hex)
    signature = bytes.fromhex(signature_hex)
    bc = model.Broadcast(
        broadcast_type=model.Broadcast.TYPE(int(broadcast_type)),
        timestamp=int(timestamp),
        data=data,
        signature=signature,
    )
    bc.verify_signature(public_key=active.BROADCAST_PUBKEY)
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
            'data_hex': bc.data.hex(),
            'created_date': common.datetime_to_timestamp_utc(bc.created_date),
        }
        for bc
        in model.Broadcast.select().order_by('created_date')
    ]
