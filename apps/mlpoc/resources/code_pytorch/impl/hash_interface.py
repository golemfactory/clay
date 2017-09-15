from hashlib import sha384 as hashing_algorithm


class Hash(object):
    HASHING_ALGORITHM = hashing_algorithm
    # digest size computation
    MAX_LAST_BYTES_NUM = hashing_algorithm(b"something").digest_size

    def __init__(self, value):
        self.value = self._compute_hash(value)

    def __repr__(self):
        return str(self.value.hex())

    @staticmethod
    def last_bytes_int(value: str, size: int) -> int:
        return Hash._int_from_bytes(value.encode()[:size])  # TODO danger here! check if it really works

    # from https://stackoverflow.com/questions/21017698/converting-int-to-bytes-in-python-3
    @staticmethod
    def _int_to_bytes(x: int):
        return x.to_bytes((x.bit_length() + 7) // 8, 'big')

    @staticmethod
    def _int_from_bytes(xbytes: bytes):
        return int.from_bytes(xbytes, 'big')


    # ------------------------- THIS METHODS SHOULD BE OVERRIDEN FOR SPECIFIC USECASES -------------------------

    @staticmethod
    def _compute_hash(value) -> bytes:
        # return bytes(sha3_256(pickle.dumps(value))) # non-determinitic
        return bytes(Hash.HASHING_ALGORITHM(hash(value)))  # python hash() is very short - only 4 bytes!
