import logging
import pathlib
import uuid

from apps.simple_manual_provider_task.simpletask import SimpleTaskDefinition
from apps.core.benchmark.benchmarkrunner import CoreBenchmark

logger = logging.getLogger(__name__)


class ManualSimpleTaskBenchmark(CoreBenchmark):
    def __init__(self):
        self._normalization_constant = 1000
        super().__init__()

        task_def = SimpleTaskDefinition()
        task_def.task_id = str(uuid.uuid4())
        task_def.resources = ['x']
        task_def.options.name = 'radek'
        task_def.options.times = 1
        self._task_definition = task_def

    @property
    def normalization_constant(self):
        return self._normalization_constant

    @property
    def task_definition(self):
        return self._task_definition

    def verify_result(self, result):
        return True
