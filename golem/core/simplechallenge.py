# Generating, solving and checking solutions of crypto-puzzles for proof of work system

from random import sample
from hashlib import sha256
import time

from golem.core.keysauth import get_random

__author__ = 'Magda.Stasiewicz'

CHALLENGE_HISTORY_LIMIT = 100
MAX_RANDINT = 100000000000000000000000000


def sha2(seed):
    """Returns hash of (string) seed as decimal
    :param str seed:
    :return int:
    """
    return int("0x" + sha256(seed).hexdigest(), 16)


def create_challenge(history, prev):
    """
    Creates puzzle by combining most recent puzzles solved, most recent puzzle challenged and random number history -
    list of pairs node_id and most recent challenge given by this node prev - most recent challenge propagated by node
    currently creating puzzle
    """
    concat = ""
    for h in history:
        concat = concat + "".join(sample(str(h[0]), min(CHALLENGE_HISTORY_LIMIT, len(h[0])))) + \
                          "".join(sample(str(h[1]), min(CHALLENGE_HISTORY_LIMIT, len(h[1]))))
    if prev:
        concat += "".join(sample(str(prev), min(CHALLENGE_HISTORY_LIMIT, len(prev))))
    concat += str(get_random(0, MAX_RANDINT))
    return concat


def solve_challenge(challenge, difficulty):
    """
    Solves the puzzle given in string challenge difficulty is required number of zeros in the beginning of binary
    representation of solution's hash returns solution and computation time in seconds
    """
    start = time.time()
    min_hash = pow(2, 256 - difficulty)     # could be done prettier
    solution = 0
    while sha2(challenge + str(solution)) > min_hash:
        solution += 1
    end = time.time()
    return solution, end - start


def accept_challenge(challenge, solution, difficulty):
    """ Returns true if solution is valid for given challenge and difficulty, false otherwise
    :param challenge:
    :param solution:
    :param int difficulty: difficulty of a challenge
    :return boolean: true if solution is valid, false otherwise
    """
    if sha2(challenge + str(solution)) <= pow(2, 256 - difficulty):     # also could be done prettier
        return True
    return False
