from golem.transactions.incomeskeeper import IncomesKeeper
from ethereum.utils import sha3, decode_hex


def _same_node(addr_info, node_id):
    if len(node_id) > 32:
        node_id = decode_hex(node_id)
    return sha3(node_id)[12:] == addr_info


        return sha3(node_id)[12:] == addr_info
