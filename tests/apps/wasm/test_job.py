import os
from contextlib import ExitStack
from json import dumps
from unittest import TestCase
from mock import mock_open, patch

from apps.wasm.resources.images.scripts import job


class WasmJobTestCase(TestCase):
    def test_job(self):
        params = {
            'name': 'test_subtask',
            'js_name': 'test.js',
            'wasm_name': 'test.wasm',
            'exec_args': ['arg1', 'arg2'],
            'input_dir_name': 'input',
            'output_file_paths': ['file1.out', 'file2.out'],
        }
        env = {
            'OUTPUT_DIR': '/output',
            'RESOURCES_DIR': '/resources',
        }

        with ExitStack() as stack:
            stack.enter_context(
                patch('builtins.open', mock_open(read_data=dumps(params))),
            )
            stack.enter_context(patch.dict('os.environ', env))
            call_mock = stack.enter_context(patch('subprocess.call'))
            job.run_job()

        expected_call = [
            job.WASM_SANDBOX_EXECUTABLE_NAME,
            '-O', '/output',
            '-I', os.path.join('/resources', 'input', 'test_subtask'),
            '-j', os.path.join('/resources', 'input', 'test.js'),
            '-w', os.path.join('/resources', 'input', 'test.wasm'),
            '-o', 'file1.out',
            '-o', 'file2.out',
            '--', 'arg1', 'arg2'
        ]
        call_mock.assert_called_once_with(expected_call, cwd='/resources')
