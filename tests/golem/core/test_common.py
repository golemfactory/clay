from unittest import TestCase

from golem.core.common import HandleKeyError


def handle_error(*args, **kwargs):
    return 6


class TestHandleKeyError(TestCase):
    h = HandleKeyError(handle_error)

    def add_to_el_in_dict(self, dict_, el, num):
        dict_[el] += num

    @h
    def test_call_with_dec(self):
        d = {'bla': 3}
        assert self.add_to_el_in_dict(d, 'kwa', 3) == 6
