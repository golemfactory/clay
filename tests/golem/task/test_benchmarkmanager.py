from unittest.mock import Mock, patch

from apps.appsmanager import AppsManager
from golem.environments.environment import Environment

from golem.model import Performance
from golem.task.benchmarkmanager import BenchmarkManager
from golem.testutils import DatabaseFixture, PEP8MixIn


class TestBenchmarkManager(DatabaseFixture, PEP8MixIn):
    PEP8_FILES = ['golem/task/benchmarkmanager.py']

    def setUp(self):
        super().setUp()
        am = AppsManager()
        am.load_all_apps()
        self.b = BenchmarkManager("NODE1", Mock(), self.path,
                                  am.get_benchmarks())

    def test_benchmarks_not_needed_wo_apps(self):
        assert not BenchmarkManager(None, None, None).benchmarks_needed()

    def test_benchmarks_needed_with_apps(self):
        assert self.b.benchmarks_needed()

    def test_benchmarks_not_needed_when_results_saved(self):
        # given
        for b_id in self.b.benchmarks:
            Performance.update_or_create(b_id, 100)

        Performance.update_or_create(Environment.get_id(), 3)

        # then
        assert not self.b.benchmarks_needed()

    @patch("golem.task.benchmarkmanager.BenchmarkManager.run_default_benchmark")
    @patch("golem.task.benchmarkmanager.BenchmarkRunner")
    def test_run_all_benchmarks(self, br_mock, rdb_mock, *_):
        # when
        self.b.run_all_benchmarks()

        # then
        assert rdb_mock.call_count == 1
        success_cb = rdb_mock.call_args[0][0]
        assert br_mock.call_count == 0
        success_cb()
        assert br_mock.call_count == 1
        success_cb2 = br_mock.call_args[0][2]  # get success callback
        success_cb2(1)
        assert br_mock.call_count == 2

    @patch("golem.task.benchmarkmanager.BenchmarkManager.run_default_benchmark")
    @patch("golem.task.benchmarkmanager.BenchmarkRunner")
    def test_run_non_default_benchmarks(self, br_mock, rdb_mock, *_):
        # given
        Performance.update_or_create(Environment.get_id(), 3)

        # when
        self.b.run_all_benchmarks()

        # then
        assert rdb_mock.call_count == 0
        assert br_mock.call_count == 1
        success_cb = br_mock.call_args[0][2]  # get success callback
        success_cb(1)
        assert br_mock.call_count == 2
