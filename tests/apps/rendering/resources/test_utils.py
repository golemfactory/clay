import unittest

from golem import testutils
from apps.rendering.resources.utils import handle_none


class TestPEP8(unittest.TestCase, testutils.PEP8MixIn):
    PEP8_FILES = ['apps/rendering/resources/utils.py']


class TestHandleNone(unittest.TestCase):

    class ExampleContextManager:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

    def test_correct(self):
        context_manager = self.ExampleContextManager()
        with handle_none(context_manager) as inner_context_manager:
            assert inner_context_manager is context_manager

    def test_none(self):
        with handle_none(None) as inner_context_manager:
            assert inner_context_manager is None

    def test_raise(self):
        with self.assertRaises(RuntimeError):
            with handle_none(None, raise_if_none=RuntimeError("fail")):
                # this should not be executed
                assert False
