# pylint: disable=protected-access
import unittest

from golem import testutils


class TestConformance(unittest.TestCase, testutils.PEP8MixIn):
    PEP8_FILES = [
        'golem/network/transport/session.py',
    ]
