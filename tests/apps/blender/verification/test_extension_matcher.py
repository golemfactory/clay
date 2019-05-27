import typing
import unittest

from apps.blender.resources.images.entrypoints.\
    scripts.verifier_tools.file_extension import matcher, types


class TestExtensionMatcher(unittest.TestCase):
    def test_bmp_expected_extension(self):
        self._assert_expected_extension(types.Bmp().extensions, '.bmp')

    def test_jpeg_expected_extension(self):
        self._assert_expected_extension(types.Jpeg().extensions, '.jpg')

    def test_tga_expected_extension(self):
        self._assert_expected_extension(types.Tga().extensions, '.tga')

    def test_unknown_extension(self):
        extension = '.unkwn'

        alias = matcher.get_expected_extension(extension)

        self.assertEqual(extension, alias)

    def _assert_expected_extension(
            self,
            aliases: typing.Iterable[str],
            expected: str
    ):
        for alias in aliases:
            self.assertEqual(matcher.get_expected_extension(alias), expected)
