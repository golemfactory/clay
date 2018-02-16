# -*- coding: utf-8 -*-

import logging
import unittest
import unittest.mock as mock

from golem.core.common import config_logging
from golem.testutils import PEP8MixIn


config_logging(suffix='_test_logging')
logger = logging.getLogger('test.logging')


class TestLogging(unittest.TestCase, PEP8MixIn):
    PEP8_FILES = [
        "golem/utils.py",
    ]

    @mock.patch('logging.Handler.handleError')
    def test_unicode_formatter(self, handleError_mock):
        problematic_s = '\xe9\x01\x03'
        msg = problematic_s + ' %s'
        logger.warning(msg, problematic_s)
        try:
            raise ValueError(problematic_s)
        except ValueError:
            logger.exception('test')
        for call in handleError_mock.call_args_list:
            # This helps in debugging. Call list will be empty if test succeeds.
            args, _kwargs = call
            record = args[0]
            print("handleError() %s:lno%d" % (record.filename, record.lineno, ))
        self.assertEqual(handleError_mock.call_count, 0)

        correct_ascii = 'Connection failure: %s'
        windows_s = 'Nie można nawiązać połączenia, ponieważ...'.encode(
            'cp1250',
        )
        logger.warning(correct_ascii, windows_s)
        self.assertEqual(handleError_mock.call_count, 0)
