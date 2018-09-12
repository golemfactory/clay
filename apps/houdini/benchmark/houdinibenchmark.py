import uuid
from os.path import join
from pathlib import Path

from apps.core.benchmark.benchmarkrunner import CoreBenchmark
from apps.houdini.houdinienvironment import HoudiniEnvironment
from apps.houdini.task.houdinitask import HoudiniTask
from apps.houdini.task.houdinitaskstate import HoudiniTaskDefinition, HoudiniTaskDefaults
from apps.houdini.task.houdiniverifier import HoudiniTaskVerifier
from golem.core.common import get_golem_path
from golem_verificator.verifier import SubtaskVerificationState




APP_DIR = join(get_golem_path(), 'apps', 'houdini')


class HoudiniBenchmark(CoreBenchmark):
    def __init__(self):
        self._normalization_constant = 1000  # TODO tweak that. issue #1356
        self.dummy_task_path = join(get_golem_path(),
                                    "apps", "houdini", "test_data")

        definition = self._task_definition = HoudiniTaskDefinition(HoudiniTaskDefaults())

        definition.task_id = str(uuid.uuid4())
        definition.total_subtasks = 8

        definition.options.scene_file = ""
        definition.options.start_frame = 30
        definition.options.end_frame = 35
        definition.options.render_node = "/out/mantra_ipr"
        definition.options.output_file = "/golem/output/output-$F4.png"


    @property
    def normalization_constant(self):
        return self._normalization_constant

    @property
    def task_definition(self):
        return self._task_definition

    def verify_result(self, result):
        return True
