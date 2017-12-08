import unittest

from golem.utils import find_free_net_port, get_raw_string


class GolemUtilsTest(unittest.TestCase):

    def test_free_port_selector(self):
        port = find_free_net_port()
        assert 1024 <= port <= 2 ** 16

    def test_get_raw_string(self):
        some_str = "\n\nsome    text \r\n with " \
                   "line \r breaks \n and  \t " \
                   "whitespaces"

        raw_str = get_raw_string(some_str)

        assert raw_str == "sometextwithlinebreaksandwhitespaces"
