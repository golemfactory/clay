import os
from os.path import join

from apps.core.benchmark.benchmarkrunner import CoreBenchmark
from apps.dummy.dummyenvironment import DummyTaskEnvironment
from apps.dummy.task.dummytask import DummyTask
from apps.dummy.task.dummytaskstate import DummyTaskDefinition, \
    DummyTaskDefaults
from apps.dummy.task.verifier import DummyTaskVerifier
from golem.core.common import get_golem_path
from golem.verification.verifier import SubtaskVerificationState

APP_DIR = join(get_golem_path(), 'apps', 'dummy')


class DummyTaskBenchmark(CoreBenchmark):
    def __init__(self):
        self._normalization_constant = 1000  # TODO tweak that
        self.dummy_task_path = join(get_golem_path(),
                                    "apps", "dummy", "test_data")

        td = self._task_definition = DummyTaskDefinition(DummyTaskDefaults())
        td.shared_data_files = [join(self.dummy_task_path, x) for x in
                                td.shared_data_files]

        td.out_file_basename = td.out_file_basename

        td.task_id = "dummy_benchmark"
        td.main_program_file = DummyTaskEnvironment().main_program_file
        td.resources = {join(self.dummy_task_path, "in.data")}
        td.add_to_resources()
        self.verifier = DummyTaskVerifier(lambda **kwargs: None)
        self.verification_options = {"difficulty": td.options.difficulty,
                                     "shared_data_files": td.shared_data_files,
                                     "result_size": td.result_size,
                                     "result_extension": DummyTask.RESULT_EXT}
        self.subtask_data = DummyTask.TESTING_CHAR * td.options.subtask_data_size  # noqa

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
            sd = self.verification_options.copy()
            sd["subtask_data"] = self.subtask_data
            sd["subtask_id"] = "DummyBenchmark"
            if ext != '.result':
                return False
            self.verifier.start_verification(sd, filepath, [], [])
            if self.verifier.state == SubtaskVerificationState.VERIFIED:
                return True
        return False