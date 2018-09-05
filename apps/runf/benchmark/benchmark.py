from os.path import join

from apps.core.benchmark.benchmarkrunner import CoreBenchmark
from apps.core.task.coretaskstate import TaskDefinition
from apps.runf.task.runftaskstate import RunFDefinition
from golem.core.common import get_golem_path

APP_DIR = join(get_golem_path(), 'apps', 'runf')


class RunFBenchmark(CoreBenchmark):
    @property
    def normalization_constant(self):
        return 1

    @property
    def task_definition(self) -> TaskDefinition:
        return RunFDefinition()

    def verify_result(self, result_data_path) -> bool:
        return True