import io
import unittest
from unittest.mock import Mock

from PIL import Image

from golem import testutils
from apps.rendering.resources.utils import handle_image_error, handle_none


class TestPEP8(unittest.TestCase, testutils.PEP8MixIn):
    PEP8_FILES = ['apps/rendering/resources/utils.py']


class TestHandleImageError(unittest.TestCase):
    def test_save_image(self):
        logger = Mock()
        with handle_image_error(logger), \
                Image.new('RGB', (1, 1)) as image, \
                io.BytesIO() as b:
            image.save(b, 'PNG')
            assert b.getvalue()
        assert not logger.error.called

    def test_save_image_key_error(self):
        logger = Mock()
        with handle_image_error(logger), \
                Image.new('RGB', (1, 1)) as image, \
                io.BytesIO() as b:
            image.save(b, 'UNKNOWN EXTENSION')
            assert b.getvalue() == b''
        assert logger.error.called

    def test_save_image_io_error(self):
        logger = Mock()
        with handle_image_error(logger), \
                Image.new('RGB', (1, 1)) as image, \
                io.BytesIO() as b:
            b.write = Mock(side_effect=IOError("fail"))
            image.save(b, 'PNG')
        assert logger.error.called


class TestHandleNone(unittest.TestCase):

    class ExampleContextManager:
        # pylint: disable=too-few-public-methods
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
