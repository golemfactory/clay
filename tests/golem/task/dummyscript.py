# Script that computes a subtask of a 'dummy task'

import random
import binascii
import hashlib


class DummyTaskResult(object):
    def __init__(self, data):
        self.data = data
        self.result_type = 0


def check_pow(pow, input_data, difficulty):
    sha = hashlib.sha256()
    sha.update(input_data)
    sha.update('%x' % pow)
    h = int(sha.hexdigest()[0:8], 16)
    return h <= difficulty


def find_pow(input_data, difficulty, result_size):
    nonce = random.getrandbits(result_size * 8)
    while True:
        if check_pow(nonce, input_data, difficulty):
            return nonce
        nonce += 1


def run_dummy_task(data_file, subtask_data, difficulty, result_size):
    """Find a string S of result_size bytes such that the hash of the contents
    of the data_file, subtask_data and S produce sha256 hash H such that
    4 leftmost bytes of H is less or equal difficulty.
    :param str data_file: file with shared task data
    :param str subtask_data: subtask-specific part of data
    :param int difficulty: required difficulty
    :param int result_size: size of the solution string S
    :rtype DummyTaskResult
    """
    with open(data_file, 'rb') as f:
        shared_input = f.readall()
    result = find_pow(shared_input + subtask_data, difficulty, result_size)
    return DummyTaskResult(result)









