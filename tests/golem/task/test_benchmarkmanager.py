import threading
from unittest.mock import Mock, patch

from pydispatch import dispatcher
from semantic_version import Version

from apps.appsmanager import AppsManager
from apps.core.benchmark.benchmarkrunner import BenchmarkRunner
import golem
from golem.environments.environment import Environment as DefaultEnvironment
from golem.model import Performance
from golem.task.benchmarkmanager import BenchmarkManager
from golem.testutils import DatabaseFixture, PEP8MixIn


class TestBenchmarkManager(DatabaseFixture, PEP8MixIn):
    PEP8_FILES = ['golem/task/benchmarkmanager.py']

    @staticmethod
    def _create_all_performance_objects(am_benchmarks):
        for b_id in am_benchmarks:
            Performance.update_or_create(b_id, 100)
        Performance.update_or_create(DefaultEnvironment.get_id(), 100)

    def test_benchmarks_needed(self):
        bm = BenchmarkManager(Mock(), Mock(), self.path, [])
        am = AppsManager(False)
        am.load_all_apps()
        bm.benchmarks = am.get_benchmarks()
        self.assertTrue(bm.benchmarks_needed())
        self._create_all_performance_objects(bm.benchmarks)
        self.assertFalse(bm.benchmarks_needed())

    def test_benchmarks_needed_after_golem_version_bump(self):
        am = AppsManager(False)
        am.load_all_apps()
        bm = BenchmarkManager(Mock(), Mock(), self.path, am.get_benchmarks())
        self._create_all_performance_objects(bm.benchmarks)
        self.assertFalse(bm.benchmarks_needed(), 'Benchmarks not needed yet')
        golem_version = Version(golem.__version__)
        with patch("golem.__version__", golem_version.next_minor()):
            self.assertTrue(
                bm.benchmarks_needed(),
                'Benchmarks needed after Golem version bump'
            )

    def test_run_benchmarks_saves_results_with_the_current_golem_version(self):
        am = AppsManager(False)
        am.load_all_apps()
        all_benchmarks = am.get_benchmarks()
        bm = BenchmarkManager(Mock(), Mock(), self.path, all_benchmarks)

        with patch.object(BenchmarkRunner, 'run',
                          lambda this, *_, **__: this.success_callback(100)):
            bm.run_benchmarks(all_benchmarks.keys())

        benchmark_results = Performance.select().execute()
        for benchmark_result in benchmark_results:
            self.assertEqual(golem.__version__, benchmark_result.golem_version)
            self.assertEqual(100, benchmark_result.value)
        self.assertEqual(len(all_benchmarks), len(benchmark_results))

    def test_run_benchmarks_dispatches_event_with_results(self):
        am = AppsManager(False)
        am.load_all_apps()
        all_benchmarks = am.get_benchmarks()
        bm = BenchmarkManager(Mock(), Mock(), self.path, all_benchmarks)

        with patch.object(dispatcher, 'send', Mock()) as dispatch_call:
            with patch.object(BenchmarkRunner, 'run',
                              lambda this, *_, **k: this.success_callback(100)):
                bm.run_benchmarks(all_benchmarks.keys())
            self.assertEqual(1, dispatch_call.call_count)
            self.assertEqual(
                set(dispatch_call.call_args[1]['results'].keys()),
                set(all_benchmarks.keys()))

    def test_run_benchmarks_calls_success_callback(self):
        am = AppsManager(False)
        am.load_all_apps()
        all_benchmarks = am.get_benchmarks()
        bm = BenchmarkManager(Mock(), Mock(), self.path, all_benchmarks)

        with patch.object(BenchmarkRunner, 'run',
                          lambda this, *_, **__: this.success_callback(100)):
            success_cb = Mock()
            bm.run_benchmarks(all_benchmarks.keys(), success_cb)
            self.assertEqual(1, success_cb.call_count)
            # pylint: disable=unsubscriptable-object
            self.assertEqual(all_benchmarks.keys(),
                             success_cb.call_args[0][0].keys())

    def test_run_benchmarks_calls_error_callback(self):
        am = AppsManager(False)
        am.load_all_apps()
        all_benchmarks = am.get_benchmarks()
        bm = BenchmarkManager(Mock(), Mock(), self.path, all_benchmarks)
        exc = Exception()

        with patch.object(BenchmarkRunner, 'run',
                          lambda this, *_, **__: this.error_callback(exc)):
            error_cb = Mock()
            bm.run_benchmarks(all_benchmarks.keys(), None, error_cb)
            self.assertEqual(1, error_cb.call_count)
            # pylint: disable=unsubscriptable-object
            self.assertEqual(exc, error_cb.call_args[0][0])

    def test_run_all_benchmarks_runs_all_apps_benchmarks_plus_default_one(self):
        am = AppsManager(False)
        am.load_all_apps()
        bm = BenchmarkManager(Mock(), Mock(), self.path, am.get_benchmarks())
        semaphore = threading.Semaphore(0)
        benchmark_thread = None

        def _default_benchmark_function(*_, **__):
            nonlocal semaphore, benchmark_thread
            benchmark_thread = threading.current_thread()
            semaphore.release()
            return 100

        with patch.object(BenchmarkRunner, 'run',
                          lambda this, *_, **__: this.success_callback(100)), \
                patch.object(DefaultEnvironment, 'DEFAULT_BENCHMARK_FUNCTION',
                             _default_benchmark_function), \
                patch.object(dispatcher, 'send', Mock()) as dispatch_call:
            bm.run_all_benchmarks()
            if semaphore.acquire(timeout=120):
                benchmark_thread.join()
                benchmark_results = Performance.select().execute()
                default_benchmark_result_found = False
                for bench_res in benchmark_results:
                    self.assertEqual(golem.__version__, bench_res.golem_version)
                    self.assertEqual(100, bench_res.value)
                    if bench_res.environment_id == DefaultEnvironment.get_id():
                        default_benchmark_result_found = True
                self.assertTrue(default_benchmark_result_found)
                self.assertEqual(1, dispatch_call.call_count)
                self.assertIn(DefaultEnvironment.get_id(),
                              dispatch_call.call_args[1]['results'])
            else:
                self.fail('Has benchmark worker thread been started at all?')

    def test_benchmark_results_are_published_on_start_if_all_available(self):
        am = AppsManager(False)
        am.load_all_apps()
        am_benchmarks = am.get_benchmarks()
        self._create_all_performance_objects(am_benchmarks)
        with patch.object(dispatcher, 'send', Mock()) as dispatch_call:
            BenchmarkManager(Mock(), Mock(), self.path, am_benchmarks)
            self.assertEqual(1, dispatch_call.call_count)
