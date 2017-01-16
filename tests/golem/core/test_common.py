import os
from unittest import TestCase

from golem.core.common import HandleKeyError, HandleAttributeError, config_logging
from golem.testutils import TempDirFixture
from mock import patch, ANY


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


class TestConfigLogging(TempDirFixture):
    """ Test config logger """

    @patch('logging.config.fileConfig')
    def test_config_logging_basestring(self, file_config):
        """ Test config when log file path is encoded as basestring """

        self.logname = os.path.join(self.path, "dir", "log.txt")
        self.dirname = os.path.dirname(self.logname)
        config_logging(self.logname)

        assert os.path.exists(self.dirname)
        file_config.assert_called_with(ANY,
                                       defaults={'logname': self.logname.encode('string-escape')},
                                       disable_existing_loggers=False)
        file_config.called = False

    @patch('logging.config.fileConfig')
    def test_config_logging_unicode(self, file_config):
        """ Test config when log file path is encoded as unicode """

        self.logname = os.path.join(self.path, "dir", "log.txt")
        self.dirname = os.path.dirname(self.logname)
        logname_u = unicode(self.logname)
        dirname_u = unicode(self.dirname)

        config_logging(logname_u)

        assert os.path.exists(dirname_u)
        file_config.assert_called_with(ANY,
                                       defaults={'logname': logname_u.encode('unicode-escape')},
                                       disable_existing_loggers=False)
        file_config.called = False

