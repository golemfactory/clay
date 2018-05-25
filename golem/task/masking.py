from functools import reduce
from hashlib import sha256
from operator import ior
import math
import random
from typing import Set, Type, TypeVar

M = TypeVar('M', bound='Mask')


class Mask:

    MASK_BYTES: int = 32  # length of mask in bytes
    MASK_LEN: int = MASK_BYTES * 8
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
        return format(self.to_int(), '0%db' % self.MASK_LEN)

    def to_bytes(self) -> bytes:
        return self.to_int().to_bytes(self.MASK_BYTES, 'big', signed=False)

    def to_int(self) -> int:
        return reduce(ior, (1 << x for x in self.bits), 0)

    def apply(self, addr: bytes) -> bool:
        return self.apply_mask(self.to_int(), addr)

    @classmethod
    def get_mask_for_task(cls: Type[M], num_subtasks: int, network_size: int) \
            -> M:
        num_bits = max(-int(math.log2(num_subtasks / network_size)), 0)
        return cls(num_bits)

    @staticmethod
    def apply_mask(mask: int, addr: bytes) -> bool:
        digest = sha256(addr).digest()
        return (int.from_bytes(digest, 'big', signed=False) & mask) == 0
