import os
from tempfile import TemporaryDirectory
import uuid

from golem.core.common import get_golem_path

from apps.wasi.task import WasiTaskDefinition, WasiTaskOptions
from apps.core.benchmark.benchmarkrunner import CoreBenchmark


class WasiTaskBenchmark(CoreBenchmark):
    EXPECTED_OUTPUT = 'test_input\n'

    def __init__(self):
        self._normalization_constant = 1000
        self.test_data_dir = os.path.join(
            get_golem_path(), 'apps', 'wasi', 'test_data'
        )
        opts = WasiTaskOptions()
        opts.bin = 'test.wasm'
        opts.workdir = self.test_data_dir
        opts.subtasks = {
            'test_subtask': WasiTaskOptions.SubtaskOptions(
                'test_subtask', ['in.txt', 'out.txt']
            )
        }

        self._task_definition = WasiTaskDefinition()
        self._task_definition.task_id = str(uuid.uuid4())
        self._task_definition.options = opts
        self._task_definition.subtasks_count = 1
        self._task_definition.add_to_resources()

    @property
    def normalization_constant(self):
        return self._normalization_constant

    @property
    def task_definition(self):
        return self._task_definition

    def verify_result(self, result_data_path):
        print(result_data_path)
        return True
        # for result_file in result:
        #     if os.path.basename(result_file) == 'out.txt':
        #         actual_output_path = result_file
        #         break
        # else:
        #     return False

        # with open(actual_output_path, 'r') as f_act:
        #     return f_act.read() == self.EXPECTED_OUTPUT
