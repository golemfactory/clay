# -*- coding: utf-8 -*-

import os
import unittest
from unittest.mock import patch, ANY, Mock
from unittest import TestCase


from golem.core.common import to_unicode, retry
from golem.core.common import HandleKeyError, HandleAttributeError, \
    config_logging, get_timestamp_utc, timestamp_to_datetime, \
    datetime_to_timestamp, timeout_to_deadline, deadline_to_timeout
from golem.testutils import PEP8MixIn
from golem.testutils import TempDirFixture


def handle_error(*args, **kwargs):
    return 6


class TestCommon(TestCase):
    def test_unicode(self):
        source = str("test string")
        result = to_unicode(source)
        assert result is source

        source = "\xd0\xd1\xd2\xd3"
        result = to_unicode(source)
        assert result is source

        source = "test string"
        result = to_unicode(source)
        assert isinstance(result, str)
        assert result == source

        source = None
        result = to_unicode(source)
        assert result is None


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

            # test with a level
            m_dconfig.reset_mock()
            t_lvl = 'WARNING'
            config_logging(suffix, datadir=datadir,
                           loglevel=t_lvl)
            self.assertEqual(m_dconfig.call_args[0][0]['root']['level'], t_lvl)

        self.assertTrue(os.path.exists(logsdir))


class TestTimestamps(unittest.TestCase):

    def test_datetime_to_timestamp(self):
        ts = get_timestamp_utc()
        assert ts
        dt = timestamp_to_datetime(ts)
        assert round(datetime_to_timestamp(dt), 5) == round(ts, 5)

    def test_deadline_to_timeout(self):
        timeout = 10**10
        ts = timeout_to_deadline(timeout)
        new_timeout = deadline_to_timeout(ts)
        assert 0 < new_timeout <= timeout


class TestRetry(unittest.TestCase):

    def test_invalid_arguments(self):
        func = Mock()

        with self.assertRaises(AssertionError):
            retry(exc_cls=None, count=3)(func)()
        with self.assertRaises(AssertionError):
            retry(ZeroDivisionError, count=-1)(func)()

    def test_retry(self):
        counter = 0

        def func():
            nonlocal counter
            counter += 1
            if counter == 1:
                raise ZeroDivisionError

        retry(ZeroDivisionError, 1)(func)()
        assert counter == 2

    def test_retry_raises(self):
        func = Mock(side_effect=ZeroDivisionError)

        with self.assertRaises(ZeroDivisionError):
            retry((IndexError, ImportError), count=10)(func)()
