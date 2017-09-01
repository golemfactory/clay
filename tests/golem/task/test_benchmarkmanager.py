from golem.task.benchmarkmanager import BenchmarkManager
from golem.testutils import DatabaseFixture, PEP8MixIn


class TestBenchmarkManager(DatabaseFixture, PEP8MixIn):
    PEP8_FILES = ['golem/task/benchmarkmanager.py']
