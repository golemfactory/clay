import types
from unittest.mock import Mock, patch

from apps.appsmanager import AppsManager
from golem.environments.environment import Environment as DefaultEnvironment
from golem.model import Performance
from golem.task.benchmarkmanager import BenchmarkManager
from golem.testutils import DatabaseFixture, PEP8MixIn


benchmarks_needed = BenchmarkManager.benchmarks_needed


class MockThread:

    def __init__(self, target=None, kwargs=None) -> None:
        self._target = target
        self._kwargs = kwargs

    def start(self):
        self._target(**self._kwargs)

    @property
    def target(self):
        return self._target


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
        # restore the original (benchmarks are disabled in conftest.py)
        self.b.benchmarks_needed = types.MethodType(benchmarks_needed, self.b)
        assert self.b.benchmarks_needed()

    def test_benchmarks_not_needed_when_results_saved(self):
        # given
        for env_id in self.b.benchmarks:
            Performance.update_or_create(env_id, 100)

        Performance.update_or_create(DefaultEnvironment.get_id(), 3)

        # then
        assert not self.b.benchmarks_needed()

    @patch("golem.task.benchmarkmanager.Thread", MockThread)
    @patch("golem.environments.environment.make_perf_test")
    @patch("golem.task.benchmarkmanager.BenchmarkRunner")
    def test_run_all_benchmarks(self, br_mock, mpt_mock, *_):
        # given
        mpt_mock.return_value = 314.15  # default performance
        # call success callback with performance = call_count * 100
        br_mock.return_value.run.side_effect = lambda: br_mock.call_args[0][2](
            br_mock.call_count * 100)

        # when
        self.b.run_all_benchmarks()

        # then
        assert mpt_mock.call_count == 1
        assert DefaultEnvironment.get_performance() == 314.15
        assert br_mock.call_count == len(self.b.benchmarks)
        for idx, env_id in enumerate(reversed(list(self.b.benchmarks))):
            assert (1 + idx) * 100 == \
                   Performance.get(Performance.environment_id == env_id).value

    @patch("golem.task.benchmarkmanager.Thread", MockThread)
    @patch("golem.environments.environment.make_perf_test")
    @patch("golem.task.benchmarkmanager.BenchmarkRunner")
    def test_run_non_default_benchmarks(self, br_mock, mpt_mock, *_):
        # given
        Performance.update_or_create(DefaultEnvironment.get_id(), -7)
        # call success callback with performance = call_count * 100
        br_mock.return_value.run.side_effect = lambda: br_mock.call_args[0][2](
            br_mock.call_count * 100)

        # when
        self.b.run_all_benchmarks()

        # then
        assert mpt_mock.call_count == 0
        assert br_mock.call_count == len(self.b.benchmarks)
        for idx, env_id in enumerate(reversed(list(self.b.benchmarks))):
            assert (1 + idx) * 100 == \
                   Performance.get(Performance.environment_id == env_id).value
