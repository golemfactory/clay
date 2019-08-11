import os
from tempfile import TemporaryDirectory
import uuid

from golem.core.common import get_golem_path

from apps.jee4g.task import Jee4gTaskDefinition, Jee4gTaskOptions
from apps.core.benchmark.benchmarkrunner import CoreBenchmark


class Jee4gTaskBenchmark(CoreBenchmark):
    EXPECTED_OUTPUT = 'Hello test!\n'

    def __init__(self):
        self._normalization_constant = 1000
        self.test_data_dir = os.path.join(
            get_golem_path(), 'apps', 'jee4g', 'test_data'
        )
        self.output_dir = TemporaryDirectory()

        opts = Jee4gTaskOptions()
        opts.input_dir = os.path.join(self.test_data_dir, 'input')
        opts.output_dir = self.output_dir.name
        opts.jar_name = 'test.jar'
        opts.subtasks = {
            'test_subtask': Jee4gTaskOptions.SubtaskOptions(
                'test_subtask', ['test'], []
            )
        }

        self._task_definition = Jee4gTaskDefinition()
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

    def verify_result(self, result):
        for result_file in result:
            if os.path.basename(result_file) == 'out.txt':
                actual_output_path = result_file
                break
        else:
            return False

        with open(actual_output_path, 'r') as f_act:
            return f_act.read() == self.EXPECTED_OUTPUT
