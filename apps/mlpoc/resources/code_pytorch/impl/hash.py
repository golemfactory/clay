# from keras.models import Sequential
from torch import nn
from .hash_interface import Hash


class PyTorchHash(Hash):
    def __init__(self, value: nn.Module):
        super().__init__(value)

    @staticmethod
    def _compute_hash(value: nn.Module):
        # for pytorch
        # this is copying data every time, in function tobytes()
        return Hash.HASHING_ALGORITHM("".join([str(v.data.numpy()) for v in value.parameters()]).encode()).digest()


class StateHash(Hash):
    def __init__(self, value):
        super().__init__(value)

    @staticmethod
    def _compute_hash(value: 'ComputationState'):
        # for state
        start_model, end_model = value.get_start_end()
        hh = lambda x: str(PyTorchHash(x.net))
        common_hash = hh(start_model) + hh(end_model)
        return Hash.HASHING_ALGORITHM(common_hash.encode()).digest()


# class KerasHash(Hash):
#
#     def __init__(self, value: Sequential):
#         super().__init__(value)
#
#     @staticmethod
#     def _compute_hash(value):
#         # for keras
#         # this is copying data every time, in function tobytes()
#         return Hash.HASHING_ALGORITHM("".join([str(hash(c.tobytes())) for v in value.layers for c in v.get_weights()]).encode()).digest()
