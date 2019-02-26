import unittest

from golem.core.variables import PROTOCOL_CONST

from .base import NodeTestBase, reuse_node_keys_default


class GolemNodeTest(NodeTestBase, unittest.TestCase):

    @reuse_node_keys_default(True)
    def test_regular_task_run(self, reuse_keys_default):
        self.reuse_node_keys_default = reuse_keys_default
        exit_code = self._run_test('golem.regular_run.RegularRun')
        self.assertEqual(exit_code, 0)

    @reuse_node_keys_default(True)
    def test_no_concent(self, reuse_keys_default):
        self.reuse_node_keys_default = reuse_keys_default
        exit_code = self._run_test('golem.no_concent.NoConcent')
        self.assertEqual(exit_code, 0)

    @reuse_node_keys_default(True)
    def test_rpc(self, reuse_keys_default):
        self.reuse_node_keys_default = reuse_keys_default
        exit_code = self._run_test('golem.rpc_test.RPCTest')
        self.assertEqual(exit_code, 0)

    @reuse_node_keys_default(True)
    def test_rpc_mainnet(self, reuse_keys_default):
        self.reuse_node_keys_default = reuse_keys_default
        exit_code = self._run_test(
            'golem.rpc_test.MainnetRPCTest', '--mainnet')
        self.assertEqual(exit_code, 0)

    @reuse_node_keys_default(True)
    def test_task_timeout(self, reuse_keys_default):
        self.reuse_node_keys_default = reuse_keys_default
        exit_code = self._run_test('golem.task_timeout.TaskTimeoutAndRestart')
        self.assertEqual(exit_code, 0)

    @reuse_node_keys_default(True)
    def test_frame_restart(self, reuse_keys_default):
        self.reuse_node_keys_default = reuse_keys_default
        exit_code = self._run_test('golem.restart_frame.RestartFrame')
        self.assertEqual(exit_code, 0)

    @unittest.skipIf(PROTOCOL_CONST.ID <= '29', "Known issue in 0.18.x")
    @reuse_node_keys_default(True)
    def test_exr(self, reuse_keys_default):
        self.reuse_node_keys_default = reuse_keys_default
        exit_code = self._run_test('golem.exr.RegularRun')
        self.assertEqual(exit_code, 0)

    @reuse_node_keys_default(True)
    def test_jpeg(self, reuse_keys_default):
        self.reuse_node_keys_default = reuse_keys_default
        exit_code = self._run_test('golem.jpeg.RegularRun')
        self.assertEqual(exit_code, 0)

    @reuse_node_keys_default(True)
    def test_jpg(self, reuse_keys_default):
        self.reuse_node_keys_default = reuse_keys_default
        exit_code = self._run_test('golem.jpg.RegularRun')
        self.assertEqual(exit_code, 0)

    @reuse_node_keys_default(True)
    def test_nested(self, reuse_keys_default):
        self.reuse_node_keys_default = reuse_keys_default
        exit_code = self._run_test(
            'golem.regular_run_stop_on_reject.RegularRun',
            **{'task-package': 'nested'}
        )
        self.assertEqual(exit_code, 0)

