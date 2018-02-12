import io
import unittest
from unittest.mock import patch

from PIL import Image

from golem import testutils
from apps.rendering.resources.utils import save_image_or_log_error


class TestPEP8(unittest.TestCase, testutils.PEP8MixIn):
    PEP8_FILES = ['apps/rendering/resources/utils.py']

    @patch('apps.rendering.resources.utils.logger')
    def test_save_image(self, logger):
        image = Image.new('RGB', (1, 1))
        b = io.BytesIO()

        save_image_or_log_error(image, b, 'PNG')

        assert not logger.exception.called
        assert b.getvalue()

    @patch('apps.rendering.resources.utils.logger')
    def test_save_image_key_error(self, logger):
        image = Image.new('RGB', (1, 1))
        b = io.BytesIO()

        save_image_or_log_error(image, b, 'UNKNOWN EXTENSION')

        assert logger.exception.called
        assert b.getvalue() == b''

    @patch('apps.rendering.resources.utils.logger')
    def test_save_image_io_error(self, logger):
        image = Image.new('RGB', (1, 1))
        b = io.BytesIO()

        def raise_IOError(*args):
            raise IOError
        b.write = raise_IOError

        save_image_or_log_error(image, b, 'PNG')

        assert logger.exception.called
