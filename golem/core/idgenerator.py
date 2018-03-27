import uuid
GEN_LEN = 6


def generate_id(gen: bytes, len_: int = GEN_LEN) -> str:
    return str(uuid.uuid1(node=gen_to_node(gen, len_)))


def generate_new_id_from_id(id_: str):
    from_uuid = uuid.UUID(id_)
    return str(uuid.uuid1(node=from_uuid.node))


def check_id_generator(id_: str, gen: bytes, len_: int = GEN_LEN):
    checked_uuid = uuid.UUID(id_)
    return gen_to_node(gen, len_) == checked_uuid.node


def gen_to_node(gen: bytes, len_: int = GEN_LEN) -> int:
    return int.from_bytes(gen[:len_], 'big')
