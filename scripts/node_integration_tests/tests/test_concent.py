import unittest
from .base import NodeTestBase, reuse_node_keys_default


class ConcentNodeTest(NodeTestBase, unittest.TestCase):

    @reuse_node_keys_default(True)
    def test_force_report(self, reuse_keys_default):
        self.reuse_node_keys_default = reuse_keys_default
        exit_code = self._run_test('concent.force_report.ForceReport')
        self.assertEqual(exit_code, 0)

    @reuse_node_keys_default(True)
    def test_force_download(self, reuse_keys_default):
        self.reuse_node_keys_default = reuse_keys_default
        exit_code = self._run_test('concent.force_download.ForceDownload')
        self.assertEqual(exit_code, 0)

    @reuse_node_keys_default(True)
    def test_force_accept(self, reuse_keys_default):
        self.reuse_node_keys_default = reuse_keys_default
        exit_code = self._run_test('concent.force_accept.ForceAccept')
        self.assertEqual(exit_code, 0)

    @reuse_node_keys_default(True)
    def test_additional_verification(self, reuse_keys_default):
        self.reuse_node_keys_default = reuse_keys_default
        exit_code = self._run_test('concent.additional_verification.AdditionalVerification')
        self.assertEqual(exit_code, 0)

    @reuse_node_keys_default(True)
    def test_force_payment(self, reuse_keys_default):
        self.reuse_node_keys_default = reuse_keys_default
        exit_code = self._run_test('concent.force_payment.ForcePayment')
        self.assertEqual(exit_code, 0)
