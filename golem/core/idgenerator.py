import uuid


GEN_LEN = 6


def generate_id(gen: bytes) -> str:
    return str(uuid.uuid1(node=gen_to_node(gen)))


def generate_new_id_from_id(id_: str):
    from_uuid = uuid.UUID(id_)
    return str(uuid.uuid1(node=from_uuid.node))


def check_id_generator(id_: str, gen: bytes):
    checked_uuid = uuid.UUID(id_)
    return gen_to_node(gen) == checked_uuid.node


def gen_to_node(gen: bytes) -> int:
    return int.from_bytes(gen[:GEN_LEN], 'big')
