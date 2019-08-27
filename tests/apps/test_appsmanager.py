from unittest import mock, TestCase

from apps.appsmanager import AppsManager
from apps.core.benchmark.benchmarkrunner import CoreBenchmark
from apps.core.task.coretask import TaskBuilder
from apps.blender.blenderenvironment import BlenderEnvironment


class TestAppsManager(TestCase):

    @staticmethod
    def _get_loaded_app_manger():
        app_manager = AppsManager()
        app_manager.load_all_apps()
        app_manager._benchmark_enabled = mock.Mock(return_value=True)
        return app_manager

    def test_get_env_list(self):
        app_manager = self._get_loaded_app_manger()
        apps = app_manager.get_env_list()
        assert any(isinstance(app, BlenderEnvironment) for app in apps)

    def test_benchmarks_in_apps(self):
        """ Are benchmarks added to apps on the list? """
        app_manager = self._get_loaded_app_manger()
        for app in app_manager.apps.values():
            assert issubclass(app.benchmark, CoreBenchmark)

    def test_get_benchmarks(self):
        app_manager = self._get_loaded_app_manger()
        benchmarks = app_manager.get_benchmarks()
        # We have at least 2 computational environments registered.
        # One of them is system and hardware dependent (BLENDER_NVGPU)
        assert len(benchmarks) >= 3
        # Let's check that benchmarks values are defined properly
        for benchmark in benchmarks.values():
            benchmark, builder_class = benchmark
            assert isinstance(benchmark, CoreBenchmark)
            assert issubclass(builder_class, TaskBuilder)

    def test_concent_supported_blender(self):
        app_manager = self._get_loaded_app_manger()
        self.assertTrue(app_manager.get_app('blender').concent_supported)
        self.assertTrue(app_manager.get_app('blender_nvgpu').concent_supported)

    def test_concent_not_supported_wasm(self):
        app_manager = self._get_loaded_app_manger()
        self.assertFalse(app_manager.get_app('wasm').concent_supported)

    def test_concent_not_supported_glambda(self):
        app_manager = self._get_loaded_app_manger()
        self.assertFalse(app_manager.get_app('glambda').concent_supported)
