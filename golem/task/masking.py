from functools import reduce
from operator import ior
import math
import random


def get_network_size():
    return 1000


def gen_mask(bits_num, key_size=64, key_difficulty=14):
    mask_len = key_size * 8 - key_difficulty
    assert key_size > 0
    assert 0 <= key_difficulty < key_size * 8
    assert 0 <= bits_num <= mask_len

    bits = random.sample(range(mask_len), bits_num)
    return reduce(ior, (1 << x for x in bits), 0)


def get_mask_for_task(subtasks_num, epoch=0):
    return gen_mask(-int(math.log2(subtasks_num / get_network_size())) - epoch)


def apply_mask(addr, mask):
    return (int.from_bytes(addr, 'big') & mask) == 0

