import os
from unittest import TestCase
from mock import mock_open, patch

from apps.wasm.task import WasmTaskOptions
from apps.wasm.benchmark import WasmTaskBenchmark


class WasmBenchmarkTestCase(TestCase):
    def setUp(self):
        self.benchmark = WasmTaskBenchmark()

    def test_definition(self):
        task_def = self.benchmark.task_definition
        self.assertEqual(task_def.subtasks_count, 1)
        self.assertCountEqual(
            task_def.resources,
            [os.path.join(self.benchmark.test_data_dir, 'input')],
        )

        opts: WasmTaskOptions = task_def.options
        self.assertEqual(
            opts.input_dir, os.path.join(self.benchmark.test_data_dir, 'input')
        )
        self.assertEqual(opts.js_name, 'test.js')
        self.assertEqual(opts.wasm_name, 'test.wasm')
        self.assertEqual(len(opts.subtasks), 1)
        self.assertIn('test_subtask', opts.subtasks)

        subtask: WasmTaskOptions.SubtaskOptions = opts.subtasks['test_subtask']
        self.assertEqual(subtask.name, 'test_subtask')
        self.assertEqual(subtask.exec_args, ['test_arg'])
        self.assertEqual(subtask.output_file_paths, ['out.txt'])

    def test_verification(self):
        self.assertFalse(
            self.benchmark.verify_result(['no', 'expected', 'output', 'file'])
        )

        with patch('builtins.open', mock_open(read_data='wrong_content')):
            self.assertFalse(self.benchmark.verify_result(['/path/to/out.txt']))

        good_content = WasmTaskBenchmark.EXPECTED_OUTPUT
        with patch('builtins.open', mock_open(read_data=good_content)):
            self.assertTrue(self.benchmark.verify_result(['/path/to/out.txt']))
