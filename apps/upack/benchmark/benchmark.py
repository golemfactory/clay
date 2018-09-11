import uuid
from os.path import join
from pathlib import Path

from apps.core.benchmark.benchmarkrunner import CoreBenchmark
from apps.upack.upackenvironment import UpackTaskEnvironment
from apps.upack.task.upacktask import UpackTask
from apps.upack.task.upacktaskstate import UpackTaskDefinition, \
    UpackTaskDefaults
from apps.upack.task.verifier import UpackTaskVerifier
from golem.core.common import get_golem_path
from golem_verificator.verifier import SubtaskVerificationState

APP_DIR = join(get_golem_path(), 'apps', 'upack')


class UpackTaskBenchmark(CoreBenchmark):
    def __init__(self):
        self._normalization_constant = 1000  # TODO tweak that. issue #1356
        self.upack_task_path = join(get_golem_path(),
                                    "apps", "upack", "test_data")
        td = self._task_definition = UpackTaskDefinition(UpackTaskDefaults())

        td.task_id = str(uuid.uuid4())
        td.shared_data_files = [join(self.upack_task_path, x) for x in
                                td.shared_data_files]
        td.main_program_file = UpackTaskEnvironment().main_program_file
        test_files = [
            'opls',
            'opls/etanol.pa2',
            'opls/cor.001',
            'opls/etanol.pa3',
            'opls/etanol.pa12',
            'cor.001',
            'etanol.tps',
            'demo',
            'demo/allstruc.pr2',
            'demo/pack.10',
            'demo/distcla.pr2',
            'demo/etanol.pa2',
            'demo/pack.13',
            'demo/cor.001',
            'demo/pack.23',
            'demo/pack.20',
            'demo/pack.pr1',
            'demo/cluslist.pr1',
            'demo/etanol.pa3',
            'demo/distcla.pr1',
            'demo/cluslist.pr2',
            'demo/pack.29',
            'demo/distzka.pr2',
            'demo/pack.19',
            'demo/pack.pr2',
            'demo/allstruc.pr1',
            'demo/etanol.pa12',
            'exp',
            'exp/ETANOL.CIF',
            'exp/etanol.pp',
            'exp/ETANOL01.CIF',
            'exp/etanol.spf',
            'exp/etanol01.spf',
            'etanol.tpa',
            'etanol.con.a',
            'etanol.con.s'
        ]
        test_files = [join(self.upack_task_path, t) for t in test_files]
        td.resources = {t for t in test_files}
        td.add_to_resources()

        self.verification_options = {}
        verification_data = dict()
        self.verification_options["subtask_id"] = "UpackBenchmark"
        verification_data['subtask_info'] = self.verification_options
        self.verifier = UpackTaskVerifier(verification_data)

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

