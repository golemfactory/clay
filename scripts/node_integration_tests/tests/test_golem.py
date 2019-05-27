import unittest

from golem.core.variables import PROTOCOL_CONST

from .base import NodeTestBase


class GolemNodeTest(NodeTestBase):

    def test_regular_task_run(self):
        self._run_test('golem.regular_run')

    def test_no_concent(self):
        self._run_test('golem.no_concent')

    def test_rpc(self):
        self._run_test('golem.rpc_test')

    def test_rpc_mainnet(self):
        self._run_test(
            'golem.rpc_test.mainnet', '--mainnet')

    def test_task_timeout(self):
        self._run_test('golem.task_timeout')

    def test_frame_restart(self):
        self._run_test('golem.restart_frame')

    @unittest.skipIf(PROTOCOL_CONST.ID <= '29', "Known issue in 0.18.x")
    def test_exr(self):
        self._run_test('golem.exr')

    def test_jpeg(self):
        self._run_test('golem.jpeg')

    def test_jpg(self):
        self._run_test('golem.jpg')

    def test_nested(self):
        self._run_test(
            'golem.regular_run_stop_on_reject',
            **{'task-package': 'nested'}
        )

    def test_zero_price(self):
        self._run_test('golem.zero_price')

    def test_task_output_directory(self):
        self._run_test('golem.task_output')

    def test_large_result(self):
        self._run_test(
            'golem.separate_hyperg',
            **{'task-package': 'cubes', 'task-settings': '4k'},
        )
