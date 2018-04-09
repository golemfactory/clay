import uuid


SEED_LEN = 6


def generate_id(seed: bytes) -> str:
    """
    seeds top 48 bits from given seed as node in generated uuid1
    :param bytes seed: for example `KeysAuth.public_key`
    :returns: string uuid1 based on timestamp and given seed
    """
    return str(uuid.uuid1(node=__seed_to_node(seed)))


def generate_new_id_from_id(id_: str) -> str:
    """
    seeds low 48 bits from id_ as node in generated uuid1
    :returns: uuid1 based on timestamp and id_
    """
    from_uuid = uuid.UUID(id_)
    return str(uuid.uuid1(node=from_uuid.node))


def check_id_seed(id_: str, seed: bytes) -> bool:
    try:
        checked_uuid = uuid.UUID(id_)
        return __seed_to_node(seed) == checked_uuid.node
    except ValueError:
        return False


def __seed_to_node(seed: bytes) -> int:
    return int.from_bytes(seed[:SEED_LEN], 'big')
