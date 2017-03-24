# -*- coding: utf-8 -*-

from golem.core.common import config_logging
from golem.testutils import PEP8MixIn
import logging
import mock
import unittest


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
        except:
            logger.exception('test')
        for call in handleError_mock.call_args_list:
            # This helps in debugging. Call list will be empty if test succeeds.
            args, kwargs = call
            record = args[0]
            print("handleError() %s:lno%d" % (record.filename, record.lineno, ))
        self.assertEquals(handleError_mock.call_count, 0)

        correct_ascii = u'Connection failure: %s'
        windows_s = u'Nie można nawiązać połączenia, ponieważ...'.encode('cp1250')
        logger.warning(correct_ascii, windows_s)
        self.assertEquals(handleError_mock.call_count, 0)
