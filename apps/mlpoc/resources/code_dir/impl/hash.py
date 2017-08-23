# from keras.models import Sequential
from torch import nn

from impl.config import HASHING_ALGORITHM
# from impl.model import ComputationState it is needed for type annotation, but there is cycle in dependencies...


class Hash(object):
    def __init__(self, value):
        self.value = self._compute_hash(value)

    def last_bytes_int(self, size: int) -> int:
        return self._int_from_bytes(self.value[:size])

    def __repr__(self):
        return str(self.value.hex())

    def _compute_hash(self, value) -> bytes:
        # return bytes(sha3_256(pickle.dumps(value))) # non-determinitic
        return bytes(HASHING_ALGORITHM(hash(value)))  # python hash() is very short - only 4 bytes!

    # from https://stackoverflow.com/questions/21017698/converting-int-to-bytes-in-python-3
    @staticmethod
    def _int_to_bytes(x: int):
        return x.to_bytes((x.bit_length() + 7) // 8, 'big')

    @staticmethod
    def _int_from_bytes(xbytes: bytes):
        return int.from_bytes(xbytes, 'big')


class PyTorchHash(Hash):
    def __init__(self, value: nn.Module):
        super().__init__(value)

    def _compute_hash(self, value: nn.Module):
        # for pytorch
        # this is copying data every time, in function tobytes()
        return HASHING_ALGORITHM("".join([str(v.data.numpy()) for v in value.parameters()]).encode()).digest()


class StateHash(Hash):
    def __init__(self, value):
        super().__init__(value)

    def _compute_hash(self, value):
        # for state
        start_model, end_model = value.get_start_end()
        hh = lambda x: str(PyTorchHash(x.net))
        common_hash = hh(start_model) + hh(end_model)
        return HASHING_ALGORITHM(common_hash.encode()).digest()

# class KerasHash(Hash):
#
#     def __init__(self, value: Sequential):
#         super().__init__(value)
#
#     def _compute_hash(self, value):
#         # for keras
#         # this is copying data every time, in function tobytes()
#         return HASHING_ALGORITHM("".join([str(hash(c.tobytes())) for v in value.layers for c in v.get_weights()]).encode()).digest()
