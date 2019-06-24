import os
from unittest import TestCase
from uuid import uuid4
from mock import patch

from golem_messages.factories.datastructures import p2p
from golem.task.taskstate import SubtaskStatus
from golem.testutils import TempDirFixture

from apps.wasm.task import (
    WasmBenchmarkTask,
    WasmBenchmarkTaskBuilder,
    WasmTask,
    WasmTaskBuilder,
    WasmTaskDefinition,
    WasmTaskOptions,
    WasmTaskTypeInfo
)


class WasmTaskOptionsTestCase(TestCase):
    def test_subtask_iterator(self):
        opts = WasmTaskOptions()
        opts.js_name = 'test.js'
        opts.wasm_name = 'test.wasm'
        opts.input_dir = '/input/dir'
        opts.output_dir = '/output/dir'
        opts.subtasks = {
            'test_subtask1': WasmTaskOptions.SubtaskOptions(
                'test_subtask1', ['arg1'], ['output_file1'],
            ),
            'test_subtask2': WasmTaskOptions.SubtaskOptions(
                'test_subtask2', ['arg2'], ['output_file2'],
            ),
        }

        subtask_iterator = opts.get_subtask_iterator()
        self.assertCountEqual(list(subtask_iterator), [
            (
                'test_subtask1',
                {
                    'name': 'test_subtask1',
                    'js_name': 'test.js',
                    'wasm_name': 'test.wasm',
                    'exec_args': ['arg1'],
                    'input_dir_name': 'dir',
                    'output_file_paths': ['output_file1']
                },
            ),
            (
                'test_subtask2',
                {
                    'name': 'test_subtask2',
                    'js_name': 'test.js',
                    'wasm_name': 'test.wasm',
                    'exec_args': ['arg2'],
                    'input_dir_name': 'dir',
                    'output_file_paths': ['output_file2']
                },
            ),
        ])


class WasmTaskDefinitionTestCase(TestCase):
    def test_definition_add_to_resources(self):
        task_def = WasmTaskDefinition()
        task_def.options = WasmTaskOptions()
        task_def.options.input_dir = '/input/dir'

        task_def.add_to_resources()

        self.assertCountEqual(task_def.resources, ['/input/dir'])


TEST_TASK_DEFINITION_DICT = {
    'type': 'wasm',
    'name': 'wasm',
    'bid': 1,
    'timeout': '00:10:00',
    'subtask_timeout': '00:10:00',
    'options': {
        'js_name': 'test.js',
        'wasm_name': 'test.wasm',
        'input_dir': '/input/dir',
        'output_dir': '/output/dir',
        'subtasks': {
            'subtask1': {
                'exec_args': ['arg1', 'arg2'],
                'output_file_paths': ['file1', 'file2'],
            },
            'subtask2': {
                'exec_args': ['arg3', 'arg4'],
                'output_file_paths': ['file3', 'file4'],
            },
        }
    }
}


class WasmTaskBuilderTestCase(TestCase):
    def test_build_full_definition(self):
        task_def = WasmTaskBuilder.build_full_definition(
            WasmTaskTypeInfo(), TEST_TASK_DEFINITION_DICT,
        )
        self.assertEqual(task_def.subtasks_count, 2)

        opts: WasmTaskOptions = task_def.options
        self.assertEqual(opts.input_dir, '/input/dir')
        self.assertEqual(opts.output_dir, '/output/dir')
        self.assertEqual(opts.js_name, 'test.js')
        self.assertEqual(opts.wasm_name, 'test.wasm')

        self.assertEqual(len(opts.subtasks), 2)

        self.assertIn('subtask1', opts.subtasks)
        self.assertEqual(opts.subtasks['subtask1'].name, 'subtask1')
        self.assertEqual(opts.subtasks['subtask1'].exec_args, ['arg1', 'arg2'])
        self.assertEqual(
            opts.subtasks['subtask1'].output_file_paths, ['file1', 'file2'],
        )

        self.assertIn('subtask2', opts.subtasks)
        self.assertEqual(opts.subtasks['subtask2'].name, 'subtask2')
        self.assertEqual(opts.subtasks['subtask2'].exec_args, ['arg3', 'arg4'])
        self.assertEqual(
            opts.subtasks['subtask2'].output_file_paths, ['file3', 'file4'],
        )


class WasmTaskTestCase(TempDirFixture):
    def setUp(self):
        super(WasmTaskTestCase, self).setUp()
        task_def = WasmTaskBuilder.build_full_definition(
            WasmTaskTypeInfo(), TEST_TASK_DEFINITION_DICT,
        )
        task_def.task_id = str(uuid4())
        self.task = WasmTask(
            total_tasks=2, task_definition=task_def,
            root_path='/', owner=p2p.Node(),
        )

    def test_get_next_subtask_extra_data(self):
        subt_name, subt_extra_data = self.task.get_next_subtask_extra_data()
        self.assertEqual(subt_name, 'subtask1')
        self.assertEqual(subt_extra_data, {
            'name': 'subtask1',
            'js_name': 'test.js',
            'wasm_name': 'test.wasm',
            'entrypoint': WasmTask.JOB_ENTRYPOINT,
            'exec_args': ['arg1', 'arg2'],
            'input_dir_name': 'dir',
            'output_file_paths': ['file1', 'file2'],
        })

        subt_name, subt_extra_data = self.task.get_next_subtask_extra_data()
        self.assertEqual(subt_name, 'subtask2')
        self.assertEqual(subt_extra_data, {
            'name': 'subtask2',
            'js_name': 'test.js',
            'wasm_name': 'test.wasm',
            'entrypoint': WasmTask.JOB_ENTRYPOINT,
            'exec_args': ['arg3', 'arg4'],
            'input_dir_name': 'dir',
            'output_file_paths': ['file3', 'file4'],
        })

        with self.assertRaises(StopIteration):
            self.task.get_next_subtask_extra_data()

    def test_query_extra_data(self):
        next_subtask_data = ('test_subtask', {'extra': 'data'})
        with patch(
            'apps.wasm.task.WasmTask.get_next_subtask_extra_data',
            return_value=next_subtask_data,
        ):
            data = self.task.query_extra_data(0.1337, 'test_id', 'test_name')

        self.assertEqual(data.ctd['extra_data'], {'extra': 'data'})
        self.assertEqual(self.task.subtasks_given[data.ctd['subtask_id']], {
            'extra': 'data',
            'status': SubtaskStatus.starting,
            'node_id': 'test_id',
            'subtask_id': data.ctd['subtask_id'],
        })
        self.assertEqual(
            self.task.subtask_names[data.ctd['subtask_id']], 'test_subtask',
        )

    def test_query_extra_data_for_test_task(self):
        next_subtask_data = ('test_subtask', {'extra': 'data'})
        with patch(
            'apps.wasm.task.WasmTask.get_next_subtask_extra_data',
            return_value=next_subtask_data,
        ):
            data = self.task.query_extra_data(0.1337, 'test_id', 'test_name')
        self.assertEqual(data.ctd['extra_data'], {'extra': 'data'})

    def test_accept_results(self):
        res_f = [
            os.path.join(self.tempdir, 'file1'),
            os.path.join(self.tempdir, 'file2'),
        ]
        res_f_contents = [
            bytes([0, 1, 2, 3, 4, 5]),
            bytes([0, 11, 12, 13, 14, 15]),
        ]
        exp_out_f = [
            os.path.join(self.tempdir, 'test_subtask_name', 'file1'),
            os.path.join(self.tempdir, 'test_subtask_name', 'file2'),
        ]

        for result_file_path, result_content in zip(res_f, res_f_contents):
            with open(result_file_path, 'wb') as f:
                f.write(result_content)

        self.task.subtask_names['test_subtask_id'] = 'test_subtask_name'
        self.task.options.output_dir = self.tempdir
        with patch('apps.wasm.task.CoreTask.accept_results') as super_acc_mock:
            self.task.accept_results('test_subtask_id', res_f)

        super_acc_mock.assert_called_once_with('test_subtask_id', res_f)

        for output_file_path, expected_output in zip(exp_out_f, res_f_contents):
            with open(output_file_path, 'rb') as output_file:
                self.assertEqual(output_file.read(), expected_output)


class WasmBenchmarkTaskTestCase(TestCase):
    def test_query_extra_data(self):
        task_def = WasmBenchmarkTaskBuilder.build_full_definition(
            WasmTaskTypeInfo(), TEST_TASK_DEFINITION_DICT,
        )
        task_def.task_id = str(uuid4())
        task = WasmBenchmarkTask(
            total_tasks=2, task_definition=task_def,
            root_path='/', owner=p2p.Node(),
        )

        next_subtask_data = ('test_subtask', {'extra': 'data'})
        with patch(
            'apps.wasm.task.WasmBenchmarkTask.get_next_subtask_extra_data',
            return_value=next_subtask_data,
        ):
            data = task.query_extra_data(0.1337, 'test_id', 'test_name')

        self.assertEqual(
            data.ctd['extra_data'], {'extra': 'data', 'input_dir_name': ''},
        )
