from unittest import TestCase

from apps.appsmanager import AppsManager
from apps.core.benchmark.benchmarkrunner import CoreBenchmark
from apps.core.task.coretask import TaskBuilder
from apps.blender.blenderenvironment import BlenderEnvironment
from apps.lux.luxenvironment import LuxRenderEnvironment


class TestAppsManager(TestCase):

    @staticmethod
    def _get_loaded_app_manger():
        app_manager = AppsManager()
        app_manager.load_all_apps()
        return app_manager

    def test_get_env_list(self):
        app_manager = self._get_loaded_app_manger()
        apps = app_manager.get_env_list()
        assert any(isinstance(app, BlenderEnvironment) for app in apps)
        assert any(isinstance(app, LuxRenderEnvironment) for app in apps)

    def test_benchmarks_in_apps(self):
        """ Are benchmarks added to apps on the list? """
        app_manager = self._get_loaded_app_manger()
        for app in app_manager.apps.values():
            assert issubclass(app.benchmark, CoreBenchmark)

    def test_get_benchmarks(self):
        app_manager = self._get_loaded_app_manger()
        benchmarks = app_manager.get_benchmarks()
        # We have 2 compuational envs registered
        assert len(benchmarks) == 3
        # Let's check that benchmarks values are defined properly
        for benchmark in benchmarks.values():
            benchmark, builder_class = benchmark
            assert isinstance(benchmark, CoreBenchmark)
            assert issubclass(builder_class, TaskBuilder)
