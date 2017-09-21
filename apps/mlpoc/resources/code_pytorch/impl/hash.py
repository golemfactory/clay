from torch import nn

from .hash_interface import Hash


class PyTorchHash(Hash):
    def __init__(self, value: nn.Module):
        super().__init__(value)

    @staticmethod
    def _compute_hash(value: nn.Module):
        # this is super slow, change that
        str_repr = "".join([str(v.data.numpy())
                            for v in value.parameters()])
        return Hash.HASHING_ALGORITHM(str_repr.encode()).digest()


class StateHash(Hash):
    def __init__(self, value):
        super().__init__(value)

    @staticmethod
    def _compute_hash(value: 'ComputationState'):
        start_model, end_model = value.get_start_end()
        hh = lambda x: str(PyTorchHash(x.net))

        return StateHash._merge_two_hashes(hh(start_model), hh(end_model))

    @staticmethod
    def _merge_two_hashes(start_hash, end_hash):
        common_hash = start_hash + end_hash
        return Hash.HASHING_ALGORITHM(common_hash.encode()).digest()


# from keras.models import Sequential
# class KerasHash(Hash):
#
#     def __init__(self, value: Sequential):
#         super().__init__(value)
#
#     @staticmethod
#     def _compute_hash(value):
#         # for keras
#         # this is copying data every time, in function tobytes()
#         str_repr = "".join([str(hash(c.tobytes()))
#                             for v in value.layers
#                             for c in v.get_weights()])
#         return Hash.HASHING_ALGORITHM(str_repr.encode()).digest()
