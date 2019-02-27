import uuid

from apps.core.benchmark.benchmarkrunner import CoreBenchmark
from apps.core.task.coretaskstate import TaskDefinition

class GLambdaTaskBenchmark(CoreBenchmark):
    def __init__(self):
        self._normalization_constant = 1000 
        self._task_definition = TaskDefinition()
        self._task_definition.task_id = str(uuid.uuid4())

    @property
    def normalization_constant(self):
        return self._normalization_constant

    @property
    def task_definition(self):
        return self._task_definition

    def verify_result(self, result):
        return True
