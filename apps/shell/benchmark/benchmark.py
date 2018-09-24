import uuid
from os.path import join
from pathlib import Path

from apps.core.benchmark.benchmarkrunner import CoreBenchmark
from apps.shell.shellenvironment import ShellTaskEnvironment
from apps.shell.task.shelltask import ShellTask
from apps.shell.task.shelltaskstate import ShellTaskDefinition, \
    ShellTaskDefaults
from apps.shell.task.verifier import ShellTaskVerifier
from golem.core.common import get_golem_path
from golem_verificator.verifier import SubtaskVerificationState

APP_DIR = join(get_golem_path(), 'apps', 'shell')


class ShellTaskBenchmark(CoreBenchmark):
    def __init__(self):
        self._normalization_constant = 1000  # TODO tweak that. issue #1356
        self.shell_task_path = join(get_golem_path(),
                                    "apps", "shell", "resources", "benchmark")
        td = self._task_definition = ShellTaskDefinition(ShellTaskDefaults())

        td.task_id = str(uuid.uuid4())
        td.main_program_file = ShellTaskEnvironment().main_program_file
        td.resources = {td.main_program_file}
        td.add_to_resources()

        self.verification_options = {}
        verification_data = dict()
        self.verification_options["subtask_id"] = "ShellBenchmark"
        verification_data['subtask_info'] = self.verification_options
        self.verifier = ShellTaskVerifier(verification_data)

    @property
    def normalization_constant(self):
        return self._normalization_constant

    @property
    def task_definition(self):
        return self._task_definition

    def verify_result(self, result):
        sd = self.verification_options.copy()

        results = [filepath for filepath in result
                   if Path(filepath).suffix.lower() == '.result']

        verification_data = dict()
        verification_data["subtask_info"] = sd
        verification_data["results"] = results

        self.verifier.start_verification(verification_data)

        return self.verifier.state == SubtaskVerificationState.VERIFIED

