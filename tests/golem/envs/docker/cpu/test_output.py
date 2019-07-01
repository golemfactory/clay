from unittest import TestCase

from golem.envs.docker.cpu import DockerOutput


class TestDockerOutput(TestCase):

    def _generic_test(self, raw_output, exp_output, encoding=None):
        output = DockerOutput(raw_output, encoding=encoding)
        self.assertEqual(list(output), exp_output)

    def test_empty(self):
        self._generic_test(raw_output=[], exp_output=[])

    def test_multiple_empty_chunks(self):
        self._generic_test(raw_output=[b"", b"", b""], exp_output=[])

    def test_single_line(self):
        self._generic_test(raw_output=[b"test\n"], exp_output=[b"test\n"])

    def test_multiple_lines(self):
        self._generic_test(
            raw_output=[b"test\n", b"test2\n"],
            exp_output=[b"test\n", b"test2\n"])

    def test_multiline_chunk(self):
        self._generic_test(
            raw_output=[b"test\ntest", b"2\n"],
            exp_output=[b"test\n", b"test2\n"])

    def test_chunks_without_newline(self):
        self._generic_test(
            raw_output=[b"t", b"e", b"s", b"t"],
            exp_output=[b"test"])

    def test_empty_lines(self):
        self._generic_test(
            raw_output=[b"\n\n\n"],
            exp_output=[b"\n", b"\n", b"\n"])

    def test_decoding(self):
        self._generic_test(
            raw_output=["ಠ_ಠ\nʕ•ᴥ•ʔ\n".encode("utf-8")],
            exp_output=["ಠ_ಠ\n", "ʕ•ᴥ•ʔ\n"],
            encoding="utf-8")
