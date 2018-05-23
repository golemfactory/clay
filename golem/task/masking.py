from functools import reduce
from operator import ior
import math
import random
from typing import Set, Type, TypeVar

from golem.core.variables import KEY_DIFFICULTY
from golem.task.taskbase import Task

M = TypeVar('M', bound='Mask')


class Mask:

    KEY_SIZE: int = 64  # public key size in bytes
    MASK_LEN: int = KEY_SIZE * 8 - KEY_DIFFICULTY  # length of mask in bits
    ALL_BITS: Set[int] = set(range(MASK_LEN))

    def __init__(self, num_bits: int) -> None:
        assert 0 <= num_bits <= self.MASK_LEN
        self.bits: Set[int] = set(random.sample(self.ALL_BITS, num_bits))

    def increase(self, num_bits: int = 1) -> None:
        assert 0 <= num_bits <= self.MASK_LEN - self.num_bits
        self.bits |= set(random.sample(self.ALL_BITS - self.bits, num_bits))

    def decrease(self, num_bits: int = 1) -> None:
        assert 0 <= num_bits <= self.num_bits
        self.bits -= set(random.sample(self.bits, num_bits))

    @property
    def num_bits(self) -> int:
        return len(self.bits)

    def to_bin(self) -> str:
        return format(self.to_int(), '0%db' % (self.KEY_SIZE * 8))

    def to_bytes(self) -> bytes:
        return self.to_int().to_bytes(self.KEY_SIZE, 'big', signed=False)

    def to_int(self) -> int:
        return reduce(ior, (1 << x for x in self.bits), 0)

    def apply(self, addr: bytes) -> bool:
        return self.apply_mask(self.to_int(), addr)

    @classmethod
    def get_mask_for_task(cls: Type[M], task: Task) -> M:
        network_size = get_network_size()
        num_subtasks = task.get_total_tasks()
        num_bits = max(-int(math.log2(num_subtasks / network_size)), 0)
        return cls(num_bits)

    @staticmethod
    def apply_mask(mask: int, addr: bytes) -> bool:
        return (int.from_bytes(addr, 'big', signed=False) & mask) == 0


def get_network_size():
    # TODO: Get a better estimate
    return 500
