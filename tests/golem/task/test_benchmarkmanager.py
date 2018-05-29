from unittest.mock import Mock

from apps.appsmanager import AppsManager

from golem.model import Performance
from golem.task.benchmarkmanager import BenchmarkManager
from golem.testutils import DatabaseFixture, PEP8MixIn


class TestBenchmarkManager(DatabaseFixture, PEP8MixIn):
    PEP8_FILES = ['golem/task/benchmarkmanager.py']

    def test_benchmarks_needed(self):
        b = BenchmarkManager("NODE1", Mock(), self.path, [])
        # No Benchmark, no benchmark needed
        assert not b.benchmarks_needed()

        am = AppsManager()
        am.load_all_apps()
        b.benchmarks = am.get_benchmarks()
        assert b.benchmarks_needed()

        for b_id in b.benchmarks:
            Performance.update_or_create(b_id, 100)

        assert not b.benchmarks_needed()
