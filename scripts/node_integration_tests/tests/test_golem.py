import unittest

from golem.core.variables import PROTOCOL_CONST

from .base import NodeTestBase, disable_key_reuse


class GolemNodeTest(NodeTestBase):

    def test_regular_task_run(self):
        """
        runs a normal, successful task run between a single provider
        and a single requestor.
        """
        self._run_test('golem.regular_run')

    def test_regular_task_api_run(self):
        """
        runs a normal, successful task run between a single provider
        and a single requestor. On the new task_api task types
        """
        self._run_test('golem.task_api')

    def test_concent(self):
        """
        runs a normal task between a provider and a requestor
        with Concent enabled
        """
        self._run_test('golem.concent')

    def test_rpc(self):
        self._run_test('golem.rpc_test')

    def test_rpc_concent(self):
        self._run_test('golem.rpc_test.concent')

    @disable_key_reuse
    def test_rpc_mainnet(self):
        self._run_test('golem.rpc_test.mainnet', '--mainnet')

    def test_task_timeout(self):
        self._run_test('golem.task_timeout')

    def test_frame_restart(self):
        self._run_test('golem.restart_frame')

    def test_exr(self):
        """
        verifies if Golem - when supplied with `EXR` as the format - will
        render the output as EXR with the proper extension.
        """
        self._run_test('golem.exr')

    def test_jpeg(self):
        """
        verifies if Golem - when supplied with `JPEG` as the format - will
        render the output as JPEG with the proper extension.
        """
        self._run_test('golem.jpeg')

    def test_jpg(self):
        """
        verifies if Golem - when supplied with `JPG` as the format - will
        still execute a task.

        as the proper name of the format in Golem's internals is `JPEG`
        the format is treated as an _unknown_ and thus, the default `PNG`
        is used.
        """
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
            **{'task-package': 'cubes', 'task-settings': '3k-low-samples'},
        )

    def test_restart_failed_subtasks(self):
        self._run_test('golem.restart_failed_subtasks')

    def test_main_scene_file(self):
        self._run_test('golem.nested_column')

    def test_multinode_regular_run(self):
        self._run_test('golem.multinode_regular_run')

    def test_disabled_verification(self):
        self._run_test('golem.disabled_verification')

    def test_lenient_verification(self):
        self._run_test('golem.lenient_verification')

    def test_four_by_three(self):
        """
        introduces an uneven division 400 pixels -> 3 subtasks
        to test for the cropping regressions
        """
        self._run_test(
            'golem.regular_run_stop_on_reject',
            **{'task-settings': '4-by-3'}
        )

    def test_concent_provider(self):
        self._run_test('golem.concent_provider')

    def test_wasm_vbr_success(self):
        self._run_test('golem.wasm_vbr_success')

    def test_wasm_vbr_single_failure(self):
        self._run_test('golem.wasm_vbr_single_failure')

    def test_wasm_vbr_crash_provider_side(self):
        self._run_test('golem.wasm_vbr_crash_provider_side')
