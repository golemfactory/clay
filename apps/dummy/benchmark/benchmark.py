import uuid
from os.path import join
from pathlib import Path

from apps.core.benchmark.benchmarkrunner import CoreBenchmark
from apps.dummy.task.dummytask import DummyTask
from apps.dummy.task.dummytaskstate import DummyTaskDefinition
from apps.dummy.task.verifier import DummyTaskVerifier
from golem.core.common import get_golem_path
from golem.verifier.subtask_verification_state import SubtaskVerificationState


class DummyTaskBenchmark(CoreBenchmark):
    def __init__(self):
        self._normalization_constant = 1000  # TODO tweak that. issue #1356
        self.dummy_task_path = join(get_golem_path(),
                                    "apps", "dummy", "test_data")

        td = self._task_definition = DummyTaskDefinition()
        td.shared_data_files = [join(self.dummy_task_path, x) for x in
                                td.shared_data_files]

        td.out_file_basename = td.out_file_basename

        td.task_id = str(uuid.uuid4())
        td.resources = {join(self.dummy_task_path, "in.data")}
        td.add_to_resources()

        self.verification_options = {"difficulty": td.options.difficulty,
                                     "shared_data_files": td.shared_data_files,
                                     "result_size": td.result_size,
                                     "result_extension": DummyTask.RESULT_EXT}
        verification_data = dict()
        self.verification_options["subtask_id"] = "DummyBenchmark"
        verification_data['subtask_info'] = self.verification_options
        verification_data['results'] = self.dummy_task_path
        self.verifier = DummyTaskVerifier(verification_data)
        self.subtask_data = \
            DummyTask.TESTING_CHAR * td.options.subtask_data_size

    @property
    def normalization_constant(self):
        return self._normalization_constant

    @property
    def task_definition(self):
        return self._task_definition

    def verify_result(self, result):
        sd = self.verification_options.copy()
        sd["subtask_data"] = self.subtask_data

        results = [filepath for filepath in result
                   if Path(filepath).suffix.lower() == '.result']

        verification_data = dict()
        verification_data["subtask_info"] = sd
        verification_data["results"] = results

        self.verifier.start_verification()

        return self.verifier.state == SubtaskVerificationState.VERIFIED
