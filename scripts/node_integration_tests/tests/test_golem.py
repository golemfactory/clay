import unittest

from golem.core.variables import PROTOCOL_CONST

from .base import NodeTestBase


class GolemNodeTest(NodeTestBase, unittest.TestCase):

    def test_regular_task_run(self):
        exit_code = self._run_test('golem.regular_run')
        self.assertEqual(exit_code, 0)

    def test_no_concent(self):
        exit_code = self._run_test('golem.no_concent')
        self.assertEqual(exit_code, 0)

    def test_rpc(self):
        exit_code = self._run_test('golem.rpc_test')
        self.assertEqual(exit_code, 0)

    def test_rpc_mainnet(self):
        exit_code = self._run_test(
            'golem.rpc_test.mainnet', '--mainnet')
        self.assertEqual(exit_code, 0)

    def test_task_timeout(self):
        exit_code = self._run_test('golem.task_timeout')
        self.assertEqual(exit_code, 0)

    def test_frame_restart(self):
        exit_code = self._run_test('golem.restart_frame')
        self.assertEqual(exit_code, 0)

    @unittest.skipIf(PROTOCOL_CONST.ID <= '29', "Known issue in 0.18.x")
    def test_exr(self):
        exit_code = self._run_test('golem.exr')
        self.assertEqual(exit_code, 0)

    @unittest.skipIf(True, "Disabled until verification is fixed #4143")
    def test_jpeg(self):
        exit_code = self._run_test('golem.jpeg')
        self.assertEqual(exit_code, 0)

    def test_jpg(self):
        exit_code = self._run_test('golem.jpg')
        self.assertEqual(exit_code, 0)

    def test_nested(self):
        exit_code = self._run_test(
            'golem.regular_run_stop_on_reject',
            **{'task-package': 'nested'}
        )
        self.assertEqual(exit_code, 0)

    def test_zero_price(self):
        exit_code = self._run_test('golem.zero_price')
        self.assertEqual(exit_code, 0)

    def test_task_output_directory(self):
        exit_code = self._run_test('golem.task_output')
        self.assertEqual(exit_code, 0)
