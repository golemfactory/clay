import uuid
from os.path import join
from pathlib import Path

from apps.core.benchmark.benchmarkrunner import CoreBenchmark
from apps.dummy2.dummy2environment import Dummy2TaskEnvironment
from apps.dummy2.task.dummy2task import Dummy2Task
from apps.dummy2.task.dummy2taskstate import Dummy2TaskDefinition, \
    Dummy2TaskDefaults
from apps.dummy2.task.verifier import Dummy2TaskVerifier
from golem.core.common import get_golem_path
from golem_verificator.verifier import SubtaskVerificationState

APP_DIR = join(get_golem_path(), 'apps', 'dummy2')


class Dummy2TaskBenchmark(CoreBenchmark):
    def __init__(self):
        self._normalization_constant = 1000  # TODO tweak that. issue #1356
        self.dummy2_task_path = join(get_golem_path(), "apps", "dummy2",
                                     "test_data")

        td = self._task_definition = Dummy2TaskDefinition(Dummy2TaskDefaults())
        td.shared_data_files = [
            join(self.dummy2_task_path, x) for x in td.shared_data_files
        ]

        td.out_file_basename = td.out_file_basename

        td.task_id = str(uuid.uuid4())
        td.main_program_file = Dummy2TaskEnvironment().main_program_file
        td.resources = {join(self.dummy2_task_path, "in.data")}
        td.add_to_resources()

        self.verification_options = {
            "difficulty": td.options.difficulty,
            "shared_data_files": td.shared_data_files,
            "result_size": td.result_size,
            "result_extension": Dummy2Task.RESULT_EXT,
            "verification": True
        }
        verification_data = dict()
        self.verification_options["subtask_id"] = "Dummy2Benchmark"
        verification_data['subtask_info'] = self.verification_options
        self.verifier = Dummy2TaskVerifier(verification_data)
        self.subtask_data = None

    @property
    def normalization_constant(self):
        return self._normalization_constant

    @property
    def task_definition(self):
        return self._task_definition

# pylint: disable=arguments-differ
    def verify_result(self, result):
        sd = self.verification_options.copy()
        sd["subtask_data"] = self.subtask_data

        results = [
            filepath for filepath in result
            if Path(filepath).suffix.lower() == '.result'
        ]

        verification_data = dict()
        verification_data["subtask_info"] = sd
        verification_data["results"] = results

        self.verifier.start_verification(verification_data)

        return self.verifier.state == SubtaskVerificationState.VERIFIED
