import unittest

from gnr.gnrstartapp import config_logging


class TestConfigLogging(unittest.TestCase):
    def test_config_logging(self):
        config_logging()