import hashlib
import time
import itertools
import sys
import math
import string


def get_charset_permutations(size):
    charset = string.ascii_lowercase + string.ascii_uppercase + \
        string.digits + string.punctuation
    return itertools.product(charset, repeat=size)


def find_passwds(password_size, hashes, step_offset=0, step=sys.maxsize):
    assert password_size >= 0

    permutations = get_charset_permutations(password_size)
    # FIXME
    sliced_permutations = itertools.islice(
        permutations, step_offset * step, (step_offset + 1) * step)
    passwords = []
    for password in sliced_permutations:
        password = ''.join(password)
        sha = hashlib.sha256()
        sha.update(password.encode())
        if sha.hexdigest() in hashes:
            passwords.append(password)
    return passwords


def run_dummy2_task(data_file, subtask_string, difficulty, result_size):
    """Find a string S of result_size bytes such that the hash of the contents
    of the data_file, subtask_data and S produce sha256 hash H such that
    4 leftmost bytes of H is less or equal difficulty.
    :param str data_file: file with shared task data
    :param str subtask_string: subtask-specific part of data
    :param int difficulty: required difficulty
    :param int result_size: size of the solution string S
    :rtype DummyTaskResult\
    """
    print('[DUMMY TASK] computation started, data_file = ', data_file,
          ', result_size = ', result_size,
          ', difficulty = 0x%08x' % difficulty)
    t0 = time.clock()
    splitted_subtask_string = subtask_string.split()
    password_size = int(splitted_subtask_string[0])
    step_offset = int(splitted_subtask_string[1])
    subtask_count = int(splitted_subtask_string[2])
    hashes = splitted_subtask_string[4:]

    assert hashes
    assert subtask_count >= 1
    assert step_offset >= 0 and step_offset < subtask_count
    permutations_count = sum(1 for _ in get_charset_permutations(password_size))
    step = int(math.ceil(permutations_count / subtask_count))
    passwords = find_passwds(password_size, set(hashes), step_offset, step)

    print('[DUMMY TASK] computation finished, time =', time.clock() - t0, 'sec')
    print('[DUMMY TASK] computation finished, password =', passwords)

    return '\n'.join(passwords)
