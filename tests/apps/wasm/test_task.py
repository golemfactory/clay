from unittest import TestCase, mock
from uuid import uuid4

from ethereum.utils import denoms

from golem_messages.factories.datastructures import p2p
from golem.testutils import TempDirFixture

from apps.wasm.task import (
    WasmTask,
    WasmTaskBuilder,
    WasmTaskDefinition,
    WasmTaskOptions,
    WasmTaskTypeInfo
)

from .. import TaskRestartMixin


def _fake_performance():
    class FakePerformance:
        def __init__(self, value, cpu_usage):
            self.value = value
            self.cpu_usage = cpu_usage
    return FakePerformance(1.0, 1)


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
    'budget': 0.5,
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
    @mock.patch("golem.model.Performance.get",
                mock.Mock(return_value=_fake_performance()))
    def test_build_full_definition(self):
        task_def = WasmTaskBuilder.build_full_definition(
            WasmTaskTypeInfo(), TEST_TASK_DEFINITION_DICT,
        )
        self.assertEqual(task_def.subtasks_count, 2)
        self.assertEqual(task_def.budget, round(0.5 * denoms.ether))

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


class WasmTaskTestCase(TaskRestartMixin, TempDirFixture):
    @mock.patch("golem.model.Performance.get",
                mock.Mock(return_value=_fake_performance()))
    def setUp(self):
        super(WasmTaskTestCase, self).setUp()
        task_def = WasmTaskBuilder.build_full_definition(
            WasmTaskTypeInfo(), TEST_TASK_DEFINITION_DICT,
        )
        task_def.task_id = str(uuid4())
        self.task = WasmTask(
            task_definition=task_def,
            root_path='/', owner=p2p.Node(),
        )

    def test_get_next_subtask_extra_data(self):
        _, subt_extra_data =\
            self.task.subtasks[0].new_instance('node_id')

        expected_dict = {
            'js_name': 'test.js',
            'wasm_name': 'test.wasm',
            'entrypoint': WasmTask.JOB_ENTRYPOINT,
            'exec_args': ['arg1', 'arg2'],
            'input_dir_name': 'dir',
            'output_file_paths': ['file1', 'file2'],
        }

        self.assertTrue(
            all([item in subt_extra_data.items()
                 for item in expected_dict.items()])
        )

        _, subt_extra_data =\
            self.task.subtasks[1].new_instance('node_id')
        expected_dict = {
            'js_name': 'test.js',
            'wasm_name': 'test.wasm',
            'entrypoint': WasmTask.JOB_ENTRYPOINT,
            'exec_args': ['arg3', 'arg4'],
            'input_dir_name': 'dir',
            'output_file_paths': ['file3', 'file4'],
        }

        self.assertTrue(
            all([item in subt_extra_data.items()
                 for item in expected_dict.items()])
        )
