# -*- coding: utf-8 -*-

import os
import unittest
from unittest import TestCase

from mock import patch, ANY

from golem.core.common import HandleKeyError, HandleAttributeError, \
    config_logging, get_timestamp_utc, timestamp_to_datetime, \
    datetime_to_timestamp, timeout_to_deadline, deadline_to_timeout
from golem.testutils import PEP8MixIn
from golem.testutils import TempDirFixture


def handle_error(*args, **kwargs):
    return 6


class TestHandleKeyError(TestCase):
    h = HandleKeyError(handle_error)

    @staticmethod
    def add_to_el_in_dict(dict_, el, num):
        dict_[el] += num

    @h
    def test_call_with_dec(self):
        d = {'bla': 3}
        assert self.add_to_el_in_dict(d, 'kwa', 3) == 6


class TestHandleAttibuteError(TestCase):
    h = HandleAttributeError(handle_error)

    @staticmethod
    def func(x):
        x.elem = 5

    @h
    def test_call_with_dec(self):
        assert self.func("Abc") == 6


class TestConfigLogging(TempDirFixture, PEP8MixIn):
    """ Test config logger """
    PEP8_FILES = [
        "loggingconfig.py",
        "golem/core/common.py",
    ]

    def test_config_logging(self):
        """Tests wether logging is properly configured"""
        datadir = os.path.join(self.path, "data_test")
        logsdir = os.path.join(datadir, "logs")

        suffix = "_tests"
        with patch('logging.config.dictConfig') as m_dconfig:
            config_logging(suffix, datadir=datadir)
            m_dconfig.assert_called_once_with(ANY)
        self.assertTrue(os.path.exists(logsdir))


class TestTimestamps(unittest.TestCase):

    def test_datetime_to_timestamp(self):
        ts = get_timestamp_utc()
        assert ts
        dt = timestamp_to_datetime(ts)
        assert datetime_to_timestamp(dt) == ts

    def test_deadline_to_timeout(self):
        timeout = 10**10
        ts = timeout_to_deadline(timeout)
        new_timeout = deadline_to_timeout(ts)
        assert 0 < new_timeout <= timeout
