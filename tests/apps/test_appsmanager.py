import os
import shutil
from unittest import mock, TestCase

from apps.appsmanager import AppsManager
from apps.core.benchmark.benchmarkrunner import CoreBenchmark
from apps.core.task.coretask import TaskBuilder
from apps.blender.blenderenvironment import BlenderEnvironment


class TestAppsManager(TestCase):

    def setUp(self):
        super().setUp()
        self.app_manager = self._get_loaded_app_manger()
        self.benchmarks = None
        self.addCleanup(self.__clean_files)

    def __clean_files(self):
        if self.benchmarks is not None:
            if os.path.isdir(
                    self.benchmarks['DUMMYPOW'][0].task_definition.tmp_dir):
                shutil.rmtree(
                    self.benchmarks['DUMMYPOW'][0].task_definition.tmp_dir)
            if os.path.isfile(
                    self.benchmarks['BLENDER'][0].
                            task_definition.output_file):
                os.remove(
                    self.benchmarks['BLENDER'][0].
                        task_definition.output_file)
            if os.path.isfile(
                    self.benchmarks['BLENDER_NVGPU'][0].
                            task_definition.output_file):
                os.remove(
                    self.benchmarks['BLENDER_NVGPU'][0].
                        task_definition.output_file)

    @staticmethod
    def _get_loaded_app_manger():
        app_manager = AppsManager()
        app_manager.load_all_apps()
        app_manager._benchmark_enabled = mock.Mock(return_value=True)
        return app_manager

    def test_get_env_list(self):
        apps = self.app_manager.get_env_list()
        assert any(isinstance(app, BlenderEnvironment) for app in apps)

    def test_benchmarks_in_apps(self):
        """ Are benchmarks added to apps on the list? """
        for app in self.app_manager.apps.values():
            assert issubclass(app.benchmark, CoreBenchmark)

    def test_get_benchmarks(self):
        self.benchmarks = self.app_manager.get_benchmarks()
        # We have at least 2 computational environments registered.
        # One of them is system and hardware dependent (BLENDER_NVGPU)
        assert len(self.benchmarks) >= 3
        # Let's check that benchmarks values are defined properly
        for benchmark in self.benchmarks.values():
            benchmark, builder_class = benchmark
            assert isinstance(benchmark, CoreBenchmark)
            assert issubclass(builder_class, TaskBuilder)
