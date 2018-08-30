from os.path import join

from apps.core.benchmark.benchmarkrunner import CoreBenchmark
from golem.core.common import get_golem_path

APP_DIR = join(get_golem_path(), 'apps', 'runf')


class RunFkBenchmark(CoreBenchmark):
    pass