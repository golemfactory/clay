from abc import abstractmethod, ABCMeta

from impl import config
from impl.hash import Hash


class BlackBox(metaclass=ABCMeta):
    LAST_BYTES_NUM = 1 # max value config.MAX_LAST_BYTES_NUM

    @abstractmethod
    def decide(self, hash: Hash) -> bool:
        pass

assert(BlackBox.LAST_BYTES_NUM <= config.MAX_LAST_BYTES_NUM)


class SimpleBlackBox(BlackBox):
    LAST_BYTES_NUM = 1

    def __init__(self, probability: float):
        self.history = []
        self.probability = probability # probability of BlackBox saying 'save'
        self.difficulty = int(2**(8*self.LAST_BYTES_NUM) * self.probability)

    def decide(self, hash: Hash):
        self.history.append(hash)

        if hash.last_bytes_int(size=self.LAST_BYTES_NUM) <= self.difficulty:
            return True
        return False

assert(SimpleBlackBox.LAST_BYTES_NUM <= config.MAX_LAST_BYTES_NUM)