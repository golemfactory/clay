from functools import reduce
from hashlib import sha256
from operator import ior
import math
import random
from typing import Set


class Mask:

    MASK_BYTES: int = 32  # length of byte_repr in bytes
    MASK_LEN: int = MASK_BYTES * 8
    ALL_BITS: Set[int] = set(range(MASK_LEN))

    def __init__(self, byte_repr: bytes = b'\x00' * MASK_BYTES) -> None:
        self.byte_repr = byte_repr

    def increase(self, num_bits: int = 1) -> None:
        bits = self.to_bits()
        num_bits = min(num_bits, self.MASK_LEN - len(bits))
        if num_bits < 0:
            raise ValueError("num_bits must be positive")
        elif num_bits == 0:
            return  # Nothing to do

        bits |= set(random.sample(self.ALL_BITS - bits, num_bits))
        self.byte_repr = self._bits_to_bytes(bits)

    def decrease(self, num_bits: int = 1) -> None:
        bits = self.to_bits()
        num_bits = min(num_bits, len(bits))
        if num_bits < 0:
            raise ValueError("num_bits must be positive")
        elif num_bits == 0:
            return  # Nothing to do

        bits -= set(random.sample(bits, num_bits))
        self.byte_repr = self._bits_to_bytes(bits)

    @property
    def num_bits(self) -> int:
        return len(self.to_bits())

    def to_bits(self) -> Set[int]:
        int_repr = self.to_int()
        return {bit for bit in self.ALL_BITS if int_repr & (1 << bit)}

    def to_bin(self) -> str:
        return format(self.to_int(), '0%db' % self.MASK_LEN)

    def to_bytes(self) -> bytes:
        return self.byte_repr

    def to_int(self) -> int:
        return int.from_bytes(self.byte_repr, 'big', signed=False)

    def matches(self, addr: bytes) -> bool:
        digest = int.from_bytes(sha256(addr).digest(), 'big', signed=False)
        return (digest & self.to_int()) == 0

    @classmethod
    def _bits_to_bytes(cls, bits: Set[int]) -> bytes:
        int_repr = reduce(ior, (1 << x for x in bits), 0)
        return int_repr.to_bytes(cls.MASK_BYTES, 'big', signed=False)

    @classmethod
    def generate(cls, num_bits: int = 0) -> 'Mask':
        num_bits = min(num_bits, cls.MASK_LEN)
        if num_bits < 0:
            raise ValueError("num_bits must be positive")

        bits = set(random.sample(cls.ALL_BITS, num_bits))
        return cls.from_bits(bits)

    @classmethod
    def from_bits(cls, bits: Set[int]) -> 'Mask':
        byte_repr = cls._bits_to_bytes(bits)
        return Mask(byte_repr)

    @classmethod
    def from_dict(cls, dict_repr: dict) -> 'Mask':
        return Mask(**dict_repr)

    @classmethod
    def get_mask_for_task(
            cls, desired_num_workers: int, potential_num_workers: int) \
            -> 'Mask':
        if potential_num_workers < 1:
            return Mask()
        num_bits = max(
            -math.floor(math.log2(desired_num_workers / potential_num_workers)),
            0)
        return cls.generate(num_bits)
