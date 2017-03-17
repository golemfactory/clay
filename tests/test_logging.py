# -*- coding: utf-8 -*-

from golem.core.common import config_logging
import logging
import unittest


config_logging(suffix='_test_logging')
logger = logging.getLogger('test.logging')

class TestLogging(unittest.TestCase):
    def test_unicode_formatter(self):
        msg = 'ąśćłęóżźćńßżź„”ŋ’↓←→óóó %s' #.encode('cp1250')
        logger.warning(msg, 'ąść„”')
        try:
            raise ValueError('ąśćżź·½«¢µ')
        except:
            logger.exception('test')
        nameerror
