import unittest

from .base import NodeTestBase


class ConcentNodeTest(NodeTestBase, unittest.TestCase):

    def test_force_report(self):
        exit_code = self._run_test('concent.force_report.ForceReport')
        self.assertEqual(exit_code, 0)

    def test_force_download(self):
        exit_code = self._run_test('concent.force_download.ForceDownload')
        self.assertEqual(exit_code, 0)

    def test_force_accept(self):
        exit_code = self._run_test('concent.force_accept.ForceAccept')
        self.assertEqual(exit_code, 0)

    def test_additional_verification(self):
        exit_code = self._run_test('concent.additional_verification.AdditionalVerification')
        self.assertEqual(exit_code, 0)

    def test_force_payment(self):
        exit_code = self._run_test('concent.force_payment.ForcePayment')
        self.assertEqual(exit_code, 0)
