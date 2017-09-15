from abc import abstractmethod, ABCMeta

import numpy as np

from .hash_interface import Hash

class BlackBox(metaclass=ABCMeta):
    LAST_BYTES_NUM = 1  # max value config.MAX_LAST_BYTES_NUM

    @abstractmethod
    def decide(self, hash: str, **kwargs) -> bool:
        pass


assert (BlackBox.LAST_BYTES_NUM <= Hash.MAX_LAST_BYTES_NUM)


# SimpleBlackBox decisions are based on hash and difficulty
class SimpleBlackBox(BlackBox):
    LAST_BYTES_NUM = 1

    def __init__(self, probability: float):
        self.history = []
        self.probability = probability  # probability of BlackBox saying 'save'
        self.difficulty = int(2 ** (8 * self.LAST_BYTES_NUM) * self.probability)

    def decide(self, hash: str, **kwargs):
        self.history.append(hash)

        if Hash.last_bytes_int(hash, size=self.LAST_BYTES_NUM) <= self.difficulty:
            return True
        return False


# CountingBlackBox decisions are based on precomputed strategy
# as it resides on Requestor side, there is no danger in strategy being here
class CountingBlackBox(BlackBox):
    def __init__(self, probability: float, num_of_rounds: int):
        self.history = []
        self.num_of_rounds = num_of_rounds
        num_of_checked_rounds = int(probability * num_of_rounds)
        self.current_round = 0

        self.checked_rounds = np.random.choice(num_of_checked_rounds,
                                               num_of_rounds,
                                               replace=False)

    def decide(self, hash: str, epoch_num=0):
        self.history.append(hash)

        if self.current_round in self.checked_rounds:
            decision = True
        else:
            decision = False

        self.current_round += 1
        return decision
