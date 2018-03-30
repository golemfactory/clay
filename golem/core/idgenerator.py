import uuid


SEED_LEN = 6


def generate_id(seed: bytes) -> str:
    return str(uuid.uuid1(node=seed_to_node(seed)))


def generate_new_id_from_id(id_: str):
    from_uuid = uuid.UUID(id_)
    return str(uuid.uuid1(node=from_uuid.node))


def check_id_seed(id_: str, gen: bytes):
    checked_uuid = uuid.UUID(id_)
    return seed_to_node(gen) == checked_uuid.node


def seed_to_node(seed: bytes) -> int:
    return int.from_bytes(seed[:SEED_LEN], 'big')
