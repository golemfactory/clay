# Script that computes a subtask of a 'dummy task'

import random
import binascii
import hashlib

class DummyTaskResult(object):
    def __init__(self, data):
        self.data = data
        self.result_type = 0


def run_dummy_task(data_file, subtask_data, difficulty, result_size):
    """Find a string S such that the hash of the contents of the data_file,
    subtask_data and S produce sha256 hash that starts with difficulty 0's
    :param str data_file: file with shared task data
    :param str subtask_data: subtask-specific part of data
    :param int difficulty: required leading number of 0's
    :param int result_size: size of the solution string S
    :param int result_file: file to to write the solution string
    :rtype DummyTaskResult
    """

    with open(data_file, 'rb') as f:
        shared_input = f.readall()

        nonce = random.getrandbits(result_size * 8)
        done = False
        while not done:
            sha = hashlib.sha256()
            sha.update(shared_input)
            sha.update(subtask_data)
            sha.update('%x' % nonce)
            h = sha.hexdigest()










