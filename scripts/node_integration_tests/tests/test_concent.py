import unittest

from .base import NodeTestBase, disable_key_reuse


class ConcentNodeTest(NodeTestBase, unittest.TestCase):

    def test_force_report(self):
        exit_code = self._run_test('concent.force_report')
        self.assertEqual(exit_code, 0)

    def test_force_download(self):
        exit_code = self._run_test('concent.force_download')
        self.assertEqual(exit_code, 0)

    def test_force_accept(self):
        exit_code = self._run_test('concent.force_accept')
        self.assertEqual(exit_code, 0)

    def test_additional_verification(self):
        exit_code = self._run_test('concent.additional_verification')
        self.assertEqual(exit_code, 0)

    @disable_key_reuse
    def test_force_payment(self):
        exit_code = self._run_test('concent.force_payment')
        self.assertEqual(exit_code, 0)
