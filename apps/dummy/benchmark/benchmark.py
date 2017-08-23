import os
import tempfile
from os.path import join

from apps.core.benchmark.benchmarkrunner import CoreBenchmark
from apps.dummy.dummyenvironment import DummyTaskEnvironment
from apps.dummy.task.dummytask import DummyTask
from apps.dummy.task.dummytaskstate import DummyTaskDefinition, DummyTaskDefaults
from apps.dummy.task.verificator import DummyTaskVerificator
from golem.core.common import get_golem_path

APP_DIR = join(get_golem_path(), 'apps', 'dummy')


class DummyTaskBenchmark(CoreBenchmark):
    def __init__(self):
        self._normalization_constant = 1000  # TODO tweak that
        self.dummy_task_path = join(get_golem_path(), "apps", "dummy", "test_data")

        td = self._task_definition = DummyTaskDefinition(DummyTaskDefaults())
        td.shared_data_files = [join(self.dummy_task_path, x) for x in td.shared_data_files]
        # td.out_file_basename = join(tempfile.gettempdir(), td.out_file_basename)
        td.out_file_basename = td.out_file_basename

        td.task_id = u"{}".format("dummy_benchmark")
        td.main_program_file = DummyTaskEnvironment().main_program_file
        td.resources = {join(self.dummy_task_path, "in.data")}
        td.add_to_resources()
        v = self.verificator = DummyTaskVerificator()
        v.verification_options = {"difficulty": td.options.difficulty,
                                  "shared_data_files": td.shared_data_files,
                                  "result_size": td.result_size,
                                  "result_extension": DummyTask.RESULT_EXTENSION}
        self.subtask_data = DummyTask.TESTING_CHAR * td.options.subtask_data_size

    @property
    def normalization_constant(self):
        return self._normalization_constant

    @property
    def task_definition(self):
        return self._task_definition

    def verify_result(self, result):
        for filepath in result:
            root, ext = os.path.splitext(filepath)
            ext = ext.lower()
            if ext == '.result':
                if self.verificator._verify_result(None,
                                                   {"subtask_data": self.subtask_data},
                                                   filepath,
                                                   None):
                    return True
        return False